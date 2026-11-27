"""Catalog-aware adapter; the upstream simulation API remains unchanged."""
import json
import hashlib
from pathlib import Path
import numpy as np
from qtpy import QtCore

from spektrafilm_gui.controller import GuiController
from spektrafilm_gui.persistence import gui_state_to_dict
from spektrafilm_gui.state_bridge import collect_gui_state


class ScanSignals(QtCore.QObject):
    progress = QtCore.Signal(int, str, int, int)
    execution = QtCore.Signal(int, str)


class TableController(GuiController):
    library = None
    restoring = False
    rotation = 0
    photo_revision = 0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._daylight_image = None
        self._camera_balance = None
        self._base_preview_cache = None
        self.preview_divisor = 0
        self._wb_preview_pending = False
        self._completed_scans = set()
        self._wb_timer = QtCore.QTimer()
        self._wb_timer.setSingleShot(True)
        self._wb_timer.setInterval(50)
        self._wb_timer.timeout.connect(self._update_white_balance)
        self._widgets.load_raw.enable_live_white_balance(self._white_balance_changed)
        self._picker_visibility = []
        self._widgets.load_raw.pick_white_balance.toggled.connect(self._toggle_picker)
        self._widgets.load_raw.pick_white_balance.setToolTip('Enable, then click neutral grey on the input image. Click again to cancel.')
        if hasattr(self._viewer, 'mouse_drag_callbacks'):
            self._viewer.mouse_drag_callbacks.append(self._pick_white_balance)
        self.scan_signals = ScanSignals()
        self.scan_run_id = 0
        self._progress_callback = None
        self.execution_backend = 'cpu'
        self._requested_backend = 'cpu'
        self._runtime_backend = 'cpu'

    def _show_picker_layer(self):
        # The normal input_preview is deliberately hidden by every preview refresh.
        # Keep a separate display layer so queued refreshes cannot blank the picker.
        from spektrafilm_gui.controller import INPUT_PREVIEW_LAYER_NAME
        source = self._layers.image_layer(INPUT_PREVIEW_LAYER_NAME)
        if source is None:
            return False
        layer = self._layers.image_layer('white_balance_picker')
        if layer is None:
            layer = self._viewer.add_image(np.asarray(source.data).copy(), name='white_balance_picker')
        else:
            layer.data = np.asarray(source.data).copy()
        layer.scale = source.scale
        layer.translate = source.translate
        layer.contrast_limits = (0., 1.)
        layer.opacity = 1.
        for current in self._viewer.layers:
            current.visible = current is layer
        self._layers.move_layer_to_top(layer)
        self._layers.set_active_layer(layer)
        return True

    def _toggle_picker(self, enabled):
        if enabled:
            if self._current_input_image is None or self.restoring:
                self._widgets.load_raw.pick_white_balance.setChecked(False)
                return
            self._wb_timer.stop()
            self._picker_visibility = [(layer, layer.visible) for layer in self._viewer.layers]
            self._picker_active = getattr(self._viewer.layers.selection, 'active', None)
            if not self._show_picker_layer():
                self._widgets.load_raw.pick_white_balance.setChecked(False)
                return
            if self.library:
                self.library.window.statusBar().showMessage('Click a neutral grey area in the input image; click Eyedropper again to cancel.')
        else:
            self._layers.remove_layer('white_balance_picker')
            for layer, visible in self._picker_visibility:
                if any(existing is layer for existing in self._viewer.layers):
                    layer.visible = visible
            active = getattr(self, '_picker_active', None)
            if any(existing is active for existing in self._viewer.layers):
                self._layers.set_active_layer(active)
            self._picker_visibility = []

    def refresh_preview_cache(self):
        super().refresh_preview_cache()
        if self._widgets.load_raw.pick_white_balance.isChecked():
            self._show_picker_layer()

    def _pick_white_balance(self, viewer, event):
        button = self._widgets.load_raw.pick_white_balance
        if not button.isChecked() or self.restoring or self._current_input_image is None:
            return
        from spektrafilm_gui.controller import INPUT_LAYER_NAME, INPUT_PREVIEW_LAYER_NAME
        layer = next((layer for layer in reversed(list(viewer.layers))
                      if layer.name == 'white_balance_picker' and layer.visible), None)
        if layer is None:
            return
        y, x = layer.world_to_data(event.position)[-2:]
        h, w = layer.data.shape[:2]
        if not (0 <= y < h and 0 <= x < w):
            return
        source = self._daylight_image if self._daylight_image is not None else self._current_input_image
        sy, sx = int(y * source.shape[0] / h), int(x * source.shape[1] / w)
        patch = source[max(0, sy-2):sy+3, max(0, sx-2):sx+3]
        from spektrafilm_gui.live_white_balance import fit_white_balance
        state = collect_gui_state(widgets=self._widgets)
        try:
            temperature, tint = fit_white_balance(patch, np.full_like(patch, .3),
                state.input_image.io.input_color_space, state.input_image.io.input_cctf_decoding)
        except ValueError as exc:
            if self.library:
                self.library.window.statusBar().showMessage(str(exc))
            return
        raw = self._widgets.load_raw
        raw.temperature.value = temperature
        raw.tint.value = tint
        raw.white_balance.value = 'custom'
        button.setChecked(False)
        self._white_balance_changed()

    def _white_balance_changed(self, *_args):
        if not self.restoring:
            raw = self._widgets.load_raw
            mode = raw.white_balance.value
            values = (self._camera_balance if mode == 'as_shot' else
                      (6504., 1.) if mode == 'daylight' else (2850., 1.) if mode == 'tungsten' else None)
            if values is not None:
                state = raw.get_state()
                state.temperature, state.tint = values
                raw.set_state(state)
            if not self._wb_timer.isActive():
                self._wb_timer.start()

    def _update_white_balance(self):
        if self.restoring or self._current_input_image is None or (self.library and self.library.closing):
            return
        self.refresh_preview_cache()
        if self.library:
            self.library.update_histogram()
        if self._active_simulation_worker is not None:
            self._wb_preview_pending = True
        else:
            self.run_preview()

    def _replay_pending_auto_preview(self):
        if self._wb_preview_pending:
            self._wb_preview_pending = False
            self._update_white_balance()
        else:
            super()._replay_pending_auto_preview()

    def _balance(self, image):
        from spektrafilm_gui.live_white_balance import apply_white_balance
        state = collect_gui_state(widgets=self._widgets)
        return apply_white_balance(image, state.gui_only.load_raw,
                                   state.input_image.io.input_color_space,
                                   state.input_image.io.input_cctf_decoding)

    def _resize_for_preview(self, image_data, *, max_size):
        raw = self._widgets.load_raw.get_state()
        source = (self._daylight_image if raw.white_balance != 'as_shot'
                  and self._daylight_image is not None else image_data)
        divisor = self.preview_divisor
        key = (id(source), source.shape, divisor, max_size)
        if self._base_preview_cache is None or self._base_preview_cache[0] != key:
            if divisor:
                from skimage.transform import resize
                h, w = source.shape[:2]
                preview = resize(source, (max(1, h // divisor), max(1, w // divisor)),
                                 preserve_range=True, anti_aliasing=True).astype(source.dtype) if divisor > 1 else source
            else:
                preview = super()._resize_for_preview(source, max_size=max_size)
            self._base_preview_cache = (key, preview)
        return self._balance(self._base_preview_cache[1])

    def _simulation_input_image(self, *, source_layer_name):
        from spektrafilm_gui.controller import INPUT_LAYER_NAME
        image = super()._simulation_input_image(source_layer_name=source_layer_name)
        if image is not None and source_layer_name == INPUT_LAYER_NAME:
            if self._widgets.load_raw.white_balance.value != 'as_shot' and self._daylight_image is not None:
                image = self._daylight_image
            return self._balance(image)
        return image

    def scan_signature(self):
        data = gui_state_to_dict(collect_gui_state(widgets=self._widgets))
        data.pop('display', None)
        # Workflow switches do not change the rendered pixels.
        data.get('simulation', {}).pop('auto_preview', None)
        path = self._current_input_path
        try:
            stat = Path(path).stat()
            source = (str(Path(path).resolve()), stat.st_mtime_ns, stat.st_size)
        except (TypeError, OSError):
            source = (path, self.photo_revision)
        value = (source, self.rotation, self.execution_backend, data)
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    def run_scan(self):
        if self.restoring or self._active_simulation_worker is not None:
            return
        signature = self.scan_signature()
        completed = signature in self._completed_scans
        if self.library:
            completed = completed or self.library.store.get_state('scan:' + signature, '') == 'complete'
        if completed:
            from qtpy import QtWidgets as W
            answer = W.QMessageBox.question(self.library.window if self.library else None,
                'Already scanned', 'This photo has already been scanned with the same settings. Continue?',
                W.QMessageBox.Yes | W.QMessageBox.No, W.QMessageBox.No)
            if answer != W.QMessageBox.Yes:
                return
        self._wb_timer.stop()
        self._wb_preview_pending = False
        self._scan_signature = signature
        super().run_scan()

    def set_execution_backend(self, backend):
        from spektrafilm.runtime.execution import ExecutionOptions
        ExecutionOptions(backend=backend)  # Validate without importing CUDA.
        if backend == self.execution_backend:
            return
        self.execution_backend = backend
        self.request_auto_preview()

    def _set_simulation_controls_enabled(self, enabled):
        super()._set_simulation_controls_enabled(enabled)
        if self.library and hasattr(self.library, 'execution_combo'):
            self.library.execution_combo.setEnabled(enabled)

    def _execute_simulation_request(self, request):
        run_id = self.scan_run_id
        is_scan = request.mode_label == 'Scan'
        self._progress_callback = (
            lambda stage, done, total: self.scan_signals.progress.emit(run_id, stage, done, total + 1)
        ) if is_scan else None
        if is_scan:
            self.scan_signals.progress.emit(run_id, 'Preparing film model', 0, 0)
        self.scan_signals.execution.emit(run_id, f'Preparing {self._requested_backend.upper()}…')
        try:
            result = super()._execute_simulation_request(request)
            simulator = self._runtime_simulator
            status = simulator.execution_status() if hasattr(simulator, 'execution_status') else 'CPU'
            result.status_message += f' · {status}'
            self.scan_signals.execution.emit(run_id, status)
            return result
        finally:
            self._progress_callback = None

    def _process_image_with_runtime(self, image_data, params):
        from spektrafilm_gui.controller import digest_params, runtime_simulator
        from spektrafilm.runtime.execution import ExecutionOptions
        params = digest_params(params, apply_stocks_specifics=(
            self._runtime_simulator is None or self._next_runtime_digest_applies_stock_specifics))
        try:
            if self._runtime_simulator is not None and self._runtime_backend != self._requested_backend:
                if hasattr(self._runtime_simulator, 'close'):
                    self._runtime_simulator.close()
                self._runtime_simulator = None
            if self._runtime_simulator is None:
                if self._requested_backend == 'cpu':
                    self._runtime_simulator = runtime_simulator(params)
                else:
                    self._runtime_simulator = runtime_simulator(
                        params, execution=ExecutionOptions(backend=self._requested_backend))
                self._runtime_backend = self._requested_backend
            else:
                self._runtime_simulator.update_params(params)
            self._next_runtime_digest_applies_stock_specifics = False
            last_total = 0

            def report(stage, done, total):
                nonlocal last_total
                last_total = total
                self._progress_callback(stage, done, total)

            if self._progress_callback is None:
                return self._runtime_simulator.process(image_data)
            result = self._runtime_simulator.process(image_data, on_progress=report)
            self._progress_callback('Preparing display', last_total, last_total)
            return result
        except Exception:
            if self._runtime_simulator is not None and hasattr(self._runtime_simulator, 'close'):
                self._runtime_simulator.close()
            self._runtime_simulator = None
            raise

    def save_current_state_to_file(self):
        from qtpy import QtWidgets as W
        from spektrafilm_gui.persistence import save_gui_state_to_path
        from spektrafilm_gui.preset_paths import PresetPaths
        paths = PresetPaths()
        parent = self.library.window if self.library else None
        try:
            filename, _ = W.QFileDialog.getSaveFileName(parent, 'Save GUI parameters',
                            str(paths.initial_directory() / 'gui_state.json'), 'JSON (*.json)')
            if not filename:
                return
            save_gui_state_to_path(collect_gui_state(widgets=self._widgets), filename)
            paths.remember(filename)
        except (OSError, ValueError) as exc:
            W.QMessageBox.warning(parent, 'Save GUI parameters', str(exc))

    def load_state_from_file(self):
        from qtpy import QtCore, QtWidgets as W
        from spektrafilm_gui.persistence import load_gui_state_from_path
        from spektrafilm_gui.preset_paths import PresetPaths
        from spektrafilm_gui.state_bridge import apply_gui_state
        paths = PresetPaths()
        parent = self.library.window if self.library else None
        previous = collect_gui_state(widgets=self._widgets)
        try:
            filename, _ = W.QFileDialog.getOpenFileName(parent, 'Load GUI parameters',
                                str(paths.initial_directory()), 'JSON (*.json)')
            if not filename:
                return
            state = load_gui_state_from_path(filename)
            self.restoring = True
            blockers = [QtCore.QSignalBlocker(obj) for obj in parent.findChildren(QtCore.QObject)] if parent else []
            try:
                apply_gui_state(state, widgets=self._widgets)
            except (ValueError, TypeError, AttributeError):
                apply_gui_state(previous, widgets=self._widgets)
                raise
            finally:
                del blockers
                self.restoring = False
            paths.remember(filename)
            self.photo_revision += 1
            self._next_runtime_digest_applies_stock_specifics = True
            self._sync_canvas_background()
            if self.library and self.library.active_id is not None:
                self.library.open_photo(self.library.active_id, force=True)
                return
            self.refresh_preview_cache()
            self.request_auto_preview()
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            W.QMessageBox.warning(parent, 'Load GUI parameters', str(exc))

    def load_input_image(self, path):
        self.library.import_and_open(path)

    def load_raw_image(self, path):
        self.library.import_and_open(path)

    def request_auto_preview(self, *args):
        if not self.restoring and not (self.library and self.library.closing):
            super().request_auto_preview(*args)

    def _run_scheduled_auto_preview(self):
        if self.restoring or (self.library and self.library.closing):
            self._auto_preview_scheduled = False
            return
        super()._run_scheduled_auto_preview()

    def _rotate_input_image(self, *, quarter_turns):
        if self.restoring or self._current_input_image is None:
            return
        self._widgets.load_raw.pick_white_balance.setChecked(False)
        if self._daylight_image is not None:
            self._daylight_image = np.rot90(self._daylight_image, quarter_turns)
        self.rotation = (self.rotation + quarter_turns) % 4
        self.photo_revision += 1
        super()._rotate_input_image(quarter_turns=quarter_turns)

    def state_token(self):
        return (self.photo_revision, self._current_input_path, self.rotation, self.execution_backend, self.preview_divisor,
                json.dumps(gui_state_to_dict(collect_gui_state(widgets=self._widgets)), sort_keys=True))

    def _start_simulation(self, **kwargs):
        if self.restoring or (self.library and self.library.closing):
            return
        if self._active_simulation_worker is None:
            self.scan_run_id += 1
            self._requested_backend = self.execution_backend
            self._simulation_token = self.state_token()
        super()._start_simulation(**kwargs)

    def _discard_stale_result(self):
        if self.restoring or getattr(self, '_simulation_token', None) != self.state_token():
            if self.library:
                self.library.finish_scan('Scan result discarded: photo/settings changed')
            self._active_simulation_worker = None
            self._active_simulation_label = None
            self._active_simulation_reports_status = True
            self._set_simulation_controls_enabled(True)
            self._next_runtime_digest_applies_stock_specifics = True
            self._replay_pending_auto_preview()
            return True
        return False

    def _on_simulation_finished(self, result):
        if not self._discard_stale_result():
            if self._active_simulation_label == 'Scan':
                signature = getattr(self, '_scan_signature', None)
                if signature:
                    self._completed_scans.add(signature)
                    if self.library:
                        self.library.store.set_state('scan:' + signature, 'complete')
                if self.library:
                    self.library.finish_scan('SCAN complete', success=True)
            self._output_token = self._simulation_token
            super()._on_simulation_finished(result)
            if self._widgets.load_raw.pick_white_balance.isChecked():
                self._show_picker_layer()

    def _on_simulation_failed(self, message):
        if not self._discard_stale_result():
            self.scan_signals.execution.emit(self.scan_run_id, 'Calculation failed — see error details')
            if self._active_simulation_label == 'Scan' and self.library:
                self.library.finish_scan('SCAN failed')
            super()._on_simulation_failed(message)

    def save_output_layer(self):
        if self.restoring or getattr(self, '_output_token', None) != self.state_token():
            from qtpy.QtWidgets import QMessageBox
            QMessageBox.information(None, 'Export', 'Run a preview or scan for the current photo and settings first.')
            return
        super().save_output_layer()
