import numpy as np
import pytest

from spektrafilm.runtime.topology import Node, run_topology
from spektrafilm.runtime.process import Simulator


def test_progress_counts_only_reachable_steps():
    nodes = [Node(('a',), ('b',), lambda x: x + 1, 'first'),
             Node(('b',), ('c',), lambda x: x * 2, 'second'),
             Node(('c',), ('d',), lambda x: x - 1, 'third')]
    updates = []
    result = run_topology(nodes, 'b', 'c', 4, on_progress=lambda *event: updates.append(event))
    assert result == 8
    assert updates == [('second', 0, 1), ('second', 1, 1)]


def test_failed_stage_does_not_report_completion():
    def fail(image):
        raise ValueError('scan failed')
    updates = []
    with pytest.raises(ValueError):
        run_topology([Node(('a',), ('b',), fail, 'scan')], 'a', 'b', 0,
                     on_progress=lambda *event: updates.append(event))
    assert updates == [('scan', 0, 1)]


def test_runtime_progress_does_not_change_pixels(default_params, small_rgb_image):
    expected = Simulator(default_params).process(small_rgb_image)
    updates = []
    actual = Simulator(default_params).process(small_rgb_image,
                            on_progress=lambda *event: updates.append(event))
    np.testing.assert_allclose(actual, expected, atol=0, rtol=0)
    assert updates[0] == ('preprocess', 0, 6)
    assert updates[-1] == ('scanning.scan_print', 6, 6)
    assert len(updates) == 12
