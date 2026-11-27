"""Runtime UI localization. Parameter values and profile identifiers stay unchanged."""
from qtpy import QtCore, QtGui, QtWidgets as W

# Source strings are English. Lowercase lookup also covers the upstream label style.
ZH = {}
for line in '''
Settings|设置
Language|语言
Cache…|缓存…
Library|图库
Develop|显影
Folders|文件夹
Photos|照片
Import photos|导入照片
Import folder|导入文件夹
Search filenames|搜索文件名
Remove from library|从图库移除
Locate original|定位原文件
Preview size|预览尺寸
Auto|自动
Compute|计算设备
Thumbnail size|缩略图大小
ccw rotate|逆时针旋转
cw rotate|顺时针旋转
reset view|重置视图
MAIN|主要
FILM|胶片
PRINT|相纸
ADVANCED|高级
CONFIG|配置
PREVIEW|预览
SCAN|扫描
SAVE|保存
Import RGB|导入 RGB
Import Raw|导入 RAW
White balance|白平衡
Temperature|色温
Tint|色调
Lens correction|镜头校正
Eyedropper - pick neutral grey|吸管 — 选取中性灰
as_shot|拍摄时设置
daylight|日光
tungsten|钨丝灯
custom|自定义
Select file|选择文件
Reprocess raw|重新处理 RAW
Crop and upscale|裁剪与放大
Input|输入
Camera|相机
Profiles|配置档
Exposure control|曝光控制
Auto exposure|自动曝光
Auto exposure method|自动曝光方式
Exposure compensation ev|曝光补偿 EV
Print auto compensation|相纸自动补偿
Auto preview|自动预览
Scan film|扫描胶片
Scan for print|用于印相
Film profile|胶片配置档
Print profile|相纸配置档
Crop|裁剪
Crop center|裁剪中心
Crop size|裁剪尺寸
Upscale factor|放大倍数
Input color space|输入色彩空间
Apply CCTF decoding|应用传递函数解码
Spectral upsampling|光谱上采样
Input gamut compress|输入色域压缩
Output gamut compress|输出色域压缩
Output color space|输出色彩空间
Output interpolation|输出插值
Saving color space|保存色彩空间
Saving CCTF encoding|保存时编码传递函数
Gray 18% canvas|18% 灰背景
White padding|白边宽度
Use display transform|使用显示色彩转换
Preview max size|预览最大尺寸
Chemistry|化学处理
Couplers|成色剂
Developer exhaustion|显影液耗竭
Film channel swap|胶片通道交换
Print channel swap|相纸通道交换
Film gamma factor|胶片伽马系数
Gamma factor|伽马系数
Gamma factor red|红色伽马系数
Gamma factor green|绿色伽马系数
Gamma factor blue|蓝色伽马系数
Gamma factor fast|快速层伽马系数
Gamma factor slow|慢速层伽马系数
Glare|眩光
Grain|颗粒
Halation|光晕
Preflash|预闪
Scanner|扫描仪
Print exposure|印相曝光
Print illuminant|印相光源
Print M filter shift|品红滤镜偏移
Print Y filter shift|黄色滤镜偏移
m filter shift|品红滤镜偏移
y filter shift|黄色滤镜偏移
Spectral gaussian blur|光谱高斯模糊
Display|显示
Output|输出
Special|特殊
Tune|微调
Save current as default|保存当前设置为默认
Restore factory default|恢复出厂设置
Save parameters|保存参数
Load parameters|读取参数
Save GUI parameters|保存界面参数
Load GUI parameters|读取界面参数
Copy parameters|复制参数
Paste parameters to selected photos|将参数粘贴到选中照片
Settings · Cache|设置 · 缓存
Choose cache directory…|选择缓存目录…
Choose cache parent directory|选择缓存父目录
Automatically remove oldest thumbnails above limit|超过容量上限时自动清理最早的缩略图
Clear cache now|立即清理缓存
Save settings|保存设置
Cache busy|缓存正在使用
Cache|缓存
Wait for image loading/import previews to finish, then clear the cache.|请等待图像加载或导入预览完成后再清理缓存。
Include subfolders|包含子文件夹
Show photo previews|显示照片预览
Select a source folder on the left|请在左侧选择来源文件夹
No folder selected.|尚未选择文件夹。
Select all|全选
Select none|取消全选
Import selected|导入所选照片
Ctrl-click to select folders|按住 Ctrl 单击可选择多个文件夹
Cancel|取消
OK|确定
Yes|是
No|否
Close|关闭
Open|打开
Import|导入
Export|导出
Original missing|原文件缺失
Photo settings|照片设置
Could not open photo|无法打开照片
Import photo|导入照片
Remove this photo from the catalog? The original file will not be deleted.|从图库中移除此照片？原文件不会被删除。
Use Locate original in the library to reconnect this photo.|请在图库中使用“定位原文件”重新关联照片。
Select a photo from a folder or import photos to begin editing.|从文件夹中选择照片，或导入照片以开始编辑。
Import photos to start. Originals stay in their current folders.|导入照片以开始使用。原文件保留在原文件夹中。
Double-click a photo to edit.|双击照片开始编辑。
Discovering photos…|正在查找照片…
Already scanned|已扫描
This photo has already been scanned with the same settings. Continue?|此照片已使用相同设置完成过扫描。是否继续？
Run a preview or scan for the current photo and settings first.|请先使用当前照片及设置执行预览或扫描。
Click a neutral grey area in the input image; click Eyedropper again to cancel.|点击输入图像中的中性灰区域；再次点击吸管按钮可取消。
Enable, then click neutral grey on the input image. Click again to cancel.|启用后点击输入图像中的中性灰区域，再次点击按钮可取消。
Preview dimensions relative to the original. SCAN always uses full resolution.|相对于原图的预览尺寸。扫描始终使用完整分辨率。
Drag to resize the filmstrip|拖动以调整底部缩略图栏高度
RGB · White-balanced input|RGB · 白平衡后的输入图像
Choose a midtone neutral area, avoiding black and clipped highlights.|请选择中间亮度的中性灰区域，避开纯黑和过曝高光。
'''.strip().splitlines():
    source, target = line.split('|', 1)
    ZH[source.casefold()] = target

for line in """
active|启用
algorithm|算法
amount|强度
black correction|黑场校正
black level|黑位
bloom intensity|辉光强度
bloom size|辉光范围
blur|模糊
blur dye clouds um|染料云模糊（微米）
boost ev|增益 EV
boost range|增益范围
core intensity|核心强度
core size|核心范围
density min|最低密度
diffusion|柔光
diffusion size um|扩散范围（微米）
enlarger|放大机
experimental|实验性
exposure|曝光
film format mm|胶片画幅（毫米）
filter family|滤镜系列
gamma interlayer b to rg|蓝层到红绿层伽马
gamma interlayer g to rb|绿层到红蓝层伽马
gamma interlayer r to gb|红层到绿蓝层伽马
gamma samelayer rgb|RGB 同层伽马
gui parameters|界面参数
halation amount|光晕强度
halation bounce decay|光晕反射衰减
halation first sigma um|首次光晕扩散（微米）
halation n bounces|光晕反射次数
halation renormalize|光晕重新归一化
halation spatial scale|光晕空间尺度
halation strength|光晕强度
halo intensity|光环强度
halo size|光环范围
halo warmth|光环暖度
hanatos2025 adaptation surface|Hanatos2025 适应曲面
hanatos2025 adaptation window|Hanatos2025 适应窗口
inhibition interlayer|层间抑制
inhibition samelayer|同层抑制
knee|拐点
lens blur|镜头模糊
lens blur um|镜头模糊（微米）
load from file|从文件读取
micro structure|微观结构
particle area um2|颗粒面积（平方微米）
particle scale|颗粒尺度
particle scale layers|各层颗粒尺度
percent|百分比
protect ev|保护 EV
roughness|粗糙度
save current to file|保存当前设置到文件
scatter amount|散射强度
scatter core um|散射核心（微米）
scatter spatial scale|散射空间尺度
scatter tail um|散射尾部（微米）
scatter tail weight|散射尾部权重
spatial scale|空间尺度
strength|强度
sublayers active|启用子层
uniformity|均匀度
unsharp mask|反差锐化
update|更新
white correction|白场校正
white level|白位
Select photos to preview|选择要预览的照片
Finishing background work before closing…|正在完成后台任务，随后关闭…
CPU · checked on first calculation|CPU · 首次计算时检查
CUDA · checked on first calculation|CUDA · 首次计算时检查
Calculation failed — see error details|计算失败，请查看错误详情
Complete|完成
Preparing…|准备中…
Preparing CPU…|正在准备 CPU…
Preparing CUDA…|正在准备 CUDA…
SCAN complete|扫描完成
SCAN failed|扫描失败
Scan result discarded: photo/settings changed|照片或设置已改变，扫描结果已丢弃
Scan result no longer matches the selected photo/settings|扫描结果与当前照片或设置不匹配
Preparing film model|正在准备胶片模型
Preparing image|正在准备图像
Film exposure|胶片曝光
Film development|胶片显影
Print exposure|相纸曝光
Print development|相纸显影
Scanning film|扫描胶片
Scanning print|扫描相纸
Preparing display|正在准备显示
Pixel of the screen mapped 1 to 1 to the image pixel|一个屏幕像素对应一个图像像素
2 screen pixels mapped to 1 image pixel|两个屏幕像素对应一个图像像素
4 screen pixels mapped to 1 image pixel|四个屏幕像素对应一个图像像素
Camera-derived equivalent temperature (approximate Kelvin); as-shot rendering uses the original camera white balance.|从相机白平衡换算的近似色温；拍摄时设置模式使用原始相机白平衡。
RGB histogram of the white-balanced input preview; values outside 0–1 are clipped to the edges.|白平衡后输入预览的 RGB 直方图；超出 0–1 的数值归入两端。
Progress measures completed processing steps, not remaining time.|进度表示已完成的处理步骤，不代表剩余时间。
Select white balance settings, if custom you can tune temperature and tint|选择白平衡模式；自定义模式可调整色温和色调。
Temperature in Kelvin for the custom whitebalance, not used for the other white balance settings|自定义白平衡色温，单位为开尔文。
Tint value for the custom white balance, not used for the other white balance settings|自定义白平衡的色调。
Apply lens corrections|应用镜头校正
""".strip().splitlines():
    source, target = line.split('|', 1)
    ZH[source.casefold()] = target


def translate(text, language):
    if language != 'zh_CN' or not isinstance(text, str):
        return text
    if text.casefold() in ZH:
        return ZH[text.casefold()]
    # Translate message prefixes while preserving filenames, paths and error details.
    for source, target in (
        ('Loading ', '正在加载 '), ('Loaded ', '已加载 '),
        ('Load failed: ', '加载失败：'), ('Import failed: ', '导入失败：'),
        ('Could not save photo edits: ', '无法保存照片调整：'),
        ('Could not read saved settings: ', '无法读取已保存设置：'),
        ('Cache cleanup failed: ', '缓存清理失败：'),
        ('Thumbnail disk cache: ', '缩略图磁盘缓存：'),
        ('All Photos', '所有照片'), ('Missing · ', '文件缺失 · '),
        ('Preview unavailable · ', '预览不可用 · '),
    ):
        if text.startswith(source):
            return target + text[len(source):]
    import re
    for pattern, template in (
        (r'Parameters pasted to (\d+) photos', '已将参数粘贴到 {} 张照片'),
        (r'(\d+) selected files', '已选择 {} 个文件'),
        (r'Imported (\d+)/(\d+) · (\d+) new', '已导入 {}/{} · 新增 {} 张'),
        (r'(\d+) photos', '{} 张照片'),
    ):
        match = re.fullmatch(pattern, text)
        if match:
            return template.format(*match.groups())
    return text


def current_language():
    app = W.QApplication.instance()
    manager = getattr(app, '_table_localizer', None)
    return manager.language if manager else 'en'


def tr(text):
    if current_language() != 'zh_CN' or not isinstance(text, str):
        return text
    return translate(text, current_language())


class Localizer(QtCore.QObject):
    def __init__(self, window, language):
        super().__init__(window)
        self.window = window
        self.language = language
        self._pending = False
        self._applying = False
        self._disposed = False
        W.QApplication.instance().installEventFilter(self)
        # A Qt translator covers standard dialog button labels too.
        self.qt_translator = QtCore.QTranslator(self)
        location = QtCore.QLibraryInfo.location(QtCore.QLibraryInfo.TranslationsPath)
        self.qt_translator.load('qtbase_zh_CN', location)
        self.set_language(language, persist=False)

    def dispose(self):
        self._disposed = True
        app = W.QApplication.instance()
        app.removeEventFilter(self)
        app.removeTranslator(self.qt_translator)
        if getattr(app, '_table_localizer', None) is self:
            app._table_localizer = None

    def set_language(self, language, *, persist=True):
        if language not in ('en', 'zh_CN'):
            raise ValueError('Unsupported language')
        self.language = language
        app = W.QApplication.instance()
        app._table_localizer = self
        app.removeTranslator(self.qt_translator)
        if language == 'zh_CN':
            app.installTranslator(self.qt_translator)
        if persist:
            QtCore.QSettings('spektrafilm-Table', 'library').setValue('language', language)
        self.apply_all()

    def _text(self, obj, key, getter, setter):
        current = getter()
        if not isinstance(current, str) or not current:
            return
        sources = getattr(obj, '_translation_sources', {})
        source, previous = sources.get(key, (current, current))
        if current != previous:
            source = current
        translated = translate(source, self.language)
        sources[key] = (source, translated)
        obj._translation_sources = sources
        if translated != current:
            setter(translated)

    def apply_widget(self, widget):
        self._text(widget, 'tooltip', widget.toolTip, widget.setToolTip)
        self._text(widget, 'title', widget.windowTitle, widget.setWindowTitle)
        if isinstance(widget, (W.QLabel, W.QAbstractButton)):
            self._text(widget, 'text', widget.text, widget.setText)
        if isinstance(widget, W.QStatusBar):
            self._text(widget, 'message', widget.currentMessage, widget.showMessage)
        if isinstance(widget, W.QLineEdit):
            self._text(widget, 'placeholder', widget.placeholderText, widget.setPlaceholderText)
        if isinstance(widget, W.QTabBar):
            for index in range(widget.count()):
                self._text(widget, ('tab', index), lambda i=index: widget.tabText(i),
                           lambda text, i=index: widget.setTabText(i, text))
        if isinstance(widget, W.QComboBox):
            # Only combos with stable stored values; never change stock/profile IDs.
            from spektrafilm_gui.widget_editors import ProfileEnumEditor
            if not isinstance(widget, ProfileEnumEditor):
                blocker = QtCore.QSignalBlocker(widget)
                for index in range(widget.count()):
                    if widget.itemData(index) is not None:
                        self._text(widget, ('item', index), lambda i=index: widget.itemText(i),
                                   lambda text, i=index: widget.setItemText(i, text))
                del blocker
        if isinstance(widget, W.QTreeWidget):
            header = widget.headerItem()
            for i in range(header.columnCount()):
                self._text(widget, ('header', i), lambda i=i: header.text(i), lambda text, i=i: header.setText(i, text))
            def translate_catalog_item(item):
                source = item.data(0, QtCore.Qt.UserRole)
                if source == '':
                    self._text(item, 'text', lambda: item.text(0), lambda text: item.setText(0, text))
            for i in range(widget.topLevelItemCount()):
                translate_catalog_item(widget.topLevelItem(i))
        for action in widget.actions():
            self._text(action, 'text', action.text, action.setText)

    def apply_all(self):
        if self._applying or self._disposed:
            return
        self._pending = False
        self._applying = True
        try:
            for widget in W.QApplication.allWidgets():
                self.apply_widget(widget)
        finally:
            self._applying = False

    def eventFilter(self, watched, event):
        if not self._applying and event.type() in (QtCore.QEvent.Show, QtCore.QEvent.LayoutRequest):
            if not self._pending:
                self._pending = True
                QtCore.QTimer.singleShot(0, self.apply_all)
        return False


def install_language(window, language=None):
    previous = getattr(W.QApplication.instance(), '_table_localizer', None)
    if previous is not None:
        previous.dispose()
    language = language or QtCore.QSettings('spektrafilm-Table', 'library').value('language', 'zh_CN')
    return Localizer(window, language if language in ('en', 'zh_CN') else 'zh_CN')
# Additional tooltips and option labels shared by the parameter panels.
for line in '''
off|关闭
average|平均测光
center_weighted|中央重点测光
highlight_weighted|高光重点测光
matrix|矩阵测光
median|中位数测光
multi_zone|多区域测光
partial|局部测光
nearest|最近邻
linear|线性
cubic|三次插值
Add a bias to the auto-exposure of the camera.|为虚拟相机的自动曝光增加补偿。
Add glare to the print|为相纸添加眩光。
Add grain to the negative|为负片添加颗粒。
Add or not the CCTF to the saved image file|是否对保存的图像应用色彩传递函数编码。
Apply the hanatos2025 bandpass adaptation window when reconstructing spectra.|重建光谱时应用 hanatos2025 带通适应窗口。
Apply the hanatos2025 surface adaptation polynomial when reconstructing spectra.|重建光谱时应用 hanatos2025 曲面适应多项式。
Apply the inverse cctf transfer function of the color space|应用色彩空间的逆传递函数。
Apply unsharp mask to the scan, [sigma in pixel, amount].|对扫描结果应用反差锐化：[像素标准差，强度]。
Auto adjust the print exposure for the camera exposure compensation ev|根据相机曝光补偿自动调整印相曝光。
Center of the crop region in relative coordinates in x, y (0-1)|裁剪中心的相对坐标 x、y（0–1）。
Changes the exposure time set in the virtual enlarger|调整虚拟放大机的曝光时间。
Color space of the input image, will be internally converted to sRGB and negative values clipped|输入图像的色彩空间；内部转换为 sRGB 并裁去负值。
Color space of the saved image file|保存图像使用的色彩空间。
Controls how quickly the highlight boost ramps in, from 0 to 1.|控制高光增益从 0 到 1 的过渡速度。
Crop image to a fraction of the original size to preview details at full scale|裁剪原图的一部分，以原始比例预览细节。
Enable DIR coupler inhibition.|启用 DIR 成色剂抑制。
Enable black point correction applied to the scanner output.|启用扫描输出的黑点校正。
Enable halation and in-emulsion scatter.|启用光晕和乳剂内部散射。
Enable per-sublayer grain structure.|启用各子层的颗粒结构。
Enable print density-curve morphing.|启用相纸密度曲线变形。
Enable white point correction applied to the scanner output.|启用扫描输出的白点校正。
Expand the white border layer around the normalized preview frame, expressed as a fraction of the image long edge.|扩展预览图周围的白边，数值为图像长边的比例。
Film stock to simulate|选择要模拟的胶片。
Gamma factor applied to the fast sub-layer.|快速子层的伽马系数。
Gamma factor applied to the mid and slow sub-layers.|中速和慢速子层的伽马系数。
Gamma factor of the density curves of the negative, < 1 reduce contrast, > 1 increase contrast|负片密度曲线伽马系数；小于 1 降低反差，大于 1 增加反差。
Global coupled gamma multiplier for the print density curves.|相纸密度曲线的全局耦合伽马倍率。
Global multiplier on the DIR coupler inhibition matrix. 1.0 leaves the per-channel gammas as-is.|DIR 成色剂抑制矩阵的全局倍率；1.0 保持各通道伽马不变。
High-level halation size multiplier (1.0 = physical defaults). Scales the first-bounce sigma.|光晕范围倍率，缩放首次反射扩散范围；1.0 为物理默认值。
High-level halation strength multiplier (1.0 = physical defaults). Scales the per-channel halation amplitudes.|光晕强度倍率，缩放各通道振幅；1.0 为物理默认值。
High-level scatter size multiplier (1.0 = physical defaults). Scales both core and tail sigmas.|散射范围倍率，同时缩放核心与尾部；1.0 为物理默认值。
High-level scatter strength. 1.0 = full physical scatter, 0.0 = no scatter. Scales the fraction of light that undergoes in-emulsion scattering.|乳剂散射强度：1.0 为完整物理散射，0.0 为无散射。
Load and process a raw file using rawpy, output colorspace and cctf as defined in current input widget state|使用 rawpy 读取并处理 RAW；输出色彩空间和传递函数采用当前输入设置。
Long edge of the film format in millimeters, e.g. 8, 16, 35, 60, 120.|胶片画幅长边，单位毫米，例如 8、16、35、60、120。
M filter shift of the color enlarger from a neutral position, in Kodak CC units|彩色放大机品红滤镜相对中性位置的偏移，单位 Kodak CC。
Y filter shift of the color enlarger from a neutral position, in Kodak CC units|彩色放大机黄色滤镜相对中性位置的偏移，单位 Kodak CC。
Maximum highlight boost in stops.|最大高光增益，单位为曝光档。
Metering method used by the virtual camera's auto-exposure.|虚拟相机自动曝光使用的测光方式。
Minimum density of the grain, typical values (0.03-0.06)|颗粒最低密度，典型值为 0.03–0.06。
Multiplier on the cross-layer (off-diagonal) inhibition. Controls saturation enhancement from interlayer DIR effects.|层间抑制倍率，控制 DIR 层间作用带来的饱和度增强。
Multiplier on the image-plane PSF widths (all per-group lambdas). Adjust for image-format / print-size differences.|图像平面点扩散函数宽度倍率，用于适配画幅及印相尺寸。
Multiplier on the same-layer (diagonal) inhibition. Controls overall contrast / gamma reduction within each RGB layer.|同层抑制倍率，控制 RGB 各层的反差和伽马降低程度。
Napari interpolation mode used to display the output layer in the viewer.|查看器显示输出图层时使用的插值方式。
Normalized size of the crop region in x, y (0,1), as fraction of the long side.|裁剪区域的 x、y 尺寸，以图像长边的比例表示（0–1）。
Output color space of the simulation|模拟输出的色彩空间。
Per-channel gamma factor applied to the blue channel.|蓝色通道的伽马系数。
Per-channel gamma factor applied to the green channel.|绿色通道的伽马系数。
Per-channel gamma factor applied to the red channel.|红色通道的伽马系数。
Percentage of the glare light (typically 0.1-0.25)|眩光百分比，典型值为 0.1–0.25。
Preflash exposure value in ev for the print|相纸预闪曝光值，单位 EV。
Print illuminant to simulate|选择模拟的印相光源。
Print paper to simulate|选择模拟的相纸。
Protected range above midgray for the boost onset in stops.|高光增益开始前保护的中灰以上范围，单位为曝光档。
Roughness of the glare light (0-1)|眩光的粗糙度（0–1）。
Run the full simulation on the full-resolution input|以完整输入分辨率运行完整模拟。
Save the current output layer to an image file|将当前输出图层保存为图像文件。
Scale image size up to increase resolution|放大图像尺寸以增加分辨率。
Scale of particle area for the RGB layers, multiplies particle_area_um2|RGB 各层的颗粒面积倍率，乘以基础颗粒面积。
Scale of particle area for the sublayers in every color layer, multiplies particle_area_um2|每个颜色层中各子层的颗粒面积倍率。
Scan the image for print, ie white and black correction of the scanner are active, and glare is deactivated.|按印相用途扫描：启用扫描仪黑白场校正，关闭眩光。
Show a scan of the negative instead of the print|显示负片扫描结果，而非相纸结果。
Sigma in nm for Gaussian blur applied to reconstructed spectra.|重建光谱高斯模糊的标准差，单位纳米。
Sigma in um for the diffusion of the couplers, (5-20 um), controls sharpness and affects saturation.|成色剂扩散标准差（5–20 微米），控制锐度并影响饱和度。
Sigma of gaussian blur in pixels for the glare|眩光高斯模糊标准差，单位像素。
Sigma of gaussian filter in pixel for the scanner lens blur.|扫描仪镜头高斯模糊标准差，单位像素。
Target black level applied when black correction is enabled.|启用黑场校正时的目标黑位。
Target white level applied when white correction is enabled.|启用白场校正时的目标白位。
Toggle the diffusion filter (Pro-Mist family).|启用或关闭柔光滤镜（Pro-Mist 系列）。
Uniformity of the grain, typical values (0.94-0.98)|颗粒均匀度，典型值为 0.94–0.98。
Use neutral 18% gray as backgroung to judge the exposure and neutral colors|使用中性 18% 灰背景，帮助判断曝光和中性色。
Use the auto-exposure feature of the virtual camera.|使用虚拟相机自动曝光。
max size of the long edge of the preview image in pixels|预览图像长边的最大像素数。
run the simulation on a small preview and deactivates grain, halation, blurs, unsharp mask (diffusion filters are active)|使用缩小的预览图运行模拟，关闭颗粒、光晕、模糊和反差锐化；柔光滤镜仍启用。
trigger the preview after every change of gui parameters, use mouse scrollwheel on parameters field, read preview tooltip for details|每次修改参数后自动预览；可在参数框上使用鼠标滚轮调整，细节见预览提示。
'''.strip().splitlines():
    source, target = line.split('|', 1)
    ZH[source.casefold()] = target
for line in '''
Additive offset on the family's halo warmth axis. Positive = warm outer halo / cool inner halo. Energy-preserving per channel. 0 = use family default.|滤镜光环暖度偏移：正值使外圈偏暖、内圈偏冷；各通道能量守恒，0 为默认值。
Advanced. Multiplier on the bloom lambda. 1.0 = use family default.|高级：辉光范围倍率，1.0 使用滤镜默认值。
Advanced. Multiplier on the core lambda. 1.0 = use family default.|高级：核心范围倍率，1.0 使用滤镜默认值。
Advanced. Multiplier on the halo lambda. 1.0 = use family default.|高级：光环范围倍率，1.0 使用滤镜默认值。
Advanced. Multiplier on the bloom weight; the three group weights are renormalized to sum to 1. 1.0 = use family default.|高级：辉光权重倍率；三组权重会归一化为总和 1，1.0 为默认值。
Advanced. Multiplier on the core weight; the three group weights are renormalized to sum to 1. 1.0 = use family default.|高级：核心权重倍率；三组权重会归一化为总和 1，1.0 为默认值。
Advanced. Multiplier on the halo weight; the three group weights are renormalized to sum to 1. 1.0 = use family default.|高级：光环权重倍率；三组权重会归一化为总和 1，1.0 为默认值。
Area of the particles in um2, relates to ISO. Approximately 0.1 for ISO 100, 0.1 for ISO 200, 0.4 for ISO 400 and so on.|颗粒面积，单位平方微米，与 ISO 有关；参考值：ISO 100 为 0.1，ISO 200 为 0.1，ISO 400 为 0.4。
Blend all three print sub-layers toward the matched Gumbel shoulder while preserving midgray via a common horizontal offset.|将相纸的三个子层混合到匹配的 Gumbel 肩部曲线，通过共同水平偏移保持中灰。
Commercial filter stop: 0, 1/8=0.125, 1/4=0.25, 1/2=0.5, 1, 2. Maps internally to the (p_s, p_a) deflected/absorbed photon fractions.|滤镜档位：0、1/8、1/4、1/2、1、2；内部映射为散射与吸收的光子比例。
Compress input chromaticities toward the visible spectral locus before spectral upsampling. Off passes input through unchanged.|光谱上采样前将输入色度压缩到可见光谱范围；关闭时保持输入不变。
DIR inhibition from the B layer onto the R and G layers respectively (g_B->R, g_B->G).|蓝层分别对红层、绿层的 DIR 抑制（g_B->R、g_B->G）。
DIR inhibition from the G layer onto the R and B layers respectively (g_G->R, g_G->B).|绿层分别对红层、蓝层的 DIR 抑制（g_G->R、g_G->B）。
DIR inhibition from the R layer onto the G and B layers respectively (g_R->G, g_R->B).|红层分别对绿层、蓝层的 DIR 抑制（g_R->G、g_R->B）。
Decay constant of the scatter exponential tail per channel [R,G,B], in micrometers (internally approximated by a sum of Gaussians). Controls extended low-level spread within the emulsion.|RGB 各通道散射指数尾部衰减常数，单位微米；内部用高斯叠加近似，控制乳剂中的远距离低强度扩散。
If enabled, divide by (1 + sum of bounce amplitudes) so mid-grey is preserved. If disabled, halation is purely additive and subtly lifts shadows as well as highlights.|启用后除以（1 + 反射振幅总和）以保持中灰；关闭后光晕直接叠加，会轻微抬升阴影及高光。
Method to upsample the spectral resolution of the image, hanatos2025 works on the full visible locus, mallett2019 works only on sRGB (will clip input).|光谱上采样方法：hanatos2025 支持完整可见光谱范围；mallett2019 仅支持 sRGB，会裁切超范围输入。
Number of multi-bounce Gaussians summed in the halation pass. Subsequent bounces use sqrt(k)-spaced widths. Typical: 2-3.|光晕处理中叠加的反射次数；后续反射宽度按 sqrt(k) 增长，典型值为 2–3。
PSF family. pro_mist / glimmerglass / cinebloom are transparent (energy-preserving); black_pro_mist absorbs a fraction of the deflected light, lifting shadows by reducing local contrast.|点扩散函数系列：pro_mist、glimmerglass、cinebloom 保持能量；black_pro_mist 吸收部分偏折光，通过降低局部反差抬升阴影。
Parameter for micro-structure due to clumps at the molecular level, [sigma blur of micro-structure / ultimate light-resolution (0.10 um default), size of molecular clumps in nm (30 nm default)]. Only for insane magnifications.|分子团微观结构参数：[模糊标准差/极限分辨率（默认 0.10 微米），分子团尺寸（默认 30 纳米）]，仅适用于极高放大倍率。
Per-bounce amplitude decay ratio (rho). Physical range 0.3-0.7. Controls how fast the halation energy falls off between bounces.|每次反射振幅衰减比 rho，物理范围为 0.3–0.7，控制光晕能量衰减速度。
Per-channel same-layer DIR gamma (R, G, B). Effective gamma reduction of each layer's density curve.|RGB 各通道同层 DIR 伽马，表示各层密度曲线的有效伽马降低量。
Reinhard knee (threshold, limit, power) on normalized chroma C/C_max. Default (0.0, 1.0, 6.0) rolls off smoothly from the center with the asymptote on the output cube edge.|归一化色度的 Reinhard 拐点（阈值、上限、指数）；默认 (0, 1, 6) 从中心平滑压缩到输出色域边界。
Reinhard knee (threshold, limit, power). Defaults (0.0, 1.0, 6.0) apply a soft full-range roll-off that asymptotes at the spectral locus boundary.|Reinhard 拐点（阈值、上限、指数）；默认 (0, 1, 6) 对全范围柔和压缩，渐近于光谱轨迹边界。
Scale the sigma of gaussian blur in um for the dye clouds, to be used at high magnifications, (default 1)|染料云高斯模糊标准差倍率，用于高倍率放大，默认 1。
Shift the M filter of the enlarger from the neutral position for the preflash, typical values (-20-20), in Kodak CC units|预闪时放大机品红滤镜偏移，典型值为 -20–20 Kodak CC。
Shift the Y filter of the enlarger from the neutral position for the preflash, typical values (-20-20), in Kodak CC units|预闪时放大机黄色滤镜偏移，典型值为 -20–20 Kodak CC。
Sigma of gaussian blur in pixels for the grain, to be increased at high magnifications, (should be 0.8-0.9 at high resolution, reduce down to 0.6 for lower res).|颗粒高斯模糊标准差，单位像素；高分辨率建议 0.8–0.9，低分辨率可降至 0.6。
Sigma of gaussian filter in um for the camera lens blur. About 5 um for typical lenses, down to 2-4 um for high quality lenses; used for sharp input simulations without lens blur.|相机镜头模糊标准差，单位微米；普通镜头约 5，高质量镜头约 2–4，用于模拟未含镜头模糊的清晰输入。
Sigma of the first halation bounce per channel [R,G,B], in micrometers. Set by the base thickness (40-80 um for typical cine/still bases).|RGB 各通道首次光晕反射标准差，单位微米，由片基厚度决定（常见片基为 40–80 微米）。
Sigma of the scatter core Gaussian per channel [R,G,B], in micrometers. Controls fine-scale sharpness loss in the emulsion.|RGB 各通道散射核心高斯标准差，单位微米，控制乳剂中细节锐度损失。
Total back-reflection halation amplitude per channel [R,G,B] (0-1). Typical red channel: weak AH 0.02-0.08, no AH 0.08-0.25. The blue channel is usually near zero.|RGB 各通道背反射光晕总振幅（0–1）；红通道典型值：弱防光晕层 0.02–0.08，无防光晕层 0.08–0.25，蓝通道通常接近零。
Use Pillow.ImageCms to retrive the display transform (only in Windows) and apply it to the napari viewer output, if disabled the output color space is used|使用 Pillow.ImageCms 获取 Windows 显示色彩转换并应用到查看器；关闭时使用输出色彩空间。
Weight of the scatter tail Gaussian per channel [R,G,B] (0-1). Tail weight + core weight = 1. Higher values put more scattered light into the long tail.|RGB 各通道散射尾部权重（0–1），与核心权重之和为 1；越大则远距离散射光越多。
xy: radial compression in CIE 1931 chromaticity (ACES RGC family, hue-preserving). oklch: perceptual chroma reduction at constant Oklch (L, h).|xy：在 CIE 1931 色度中径向压缩并保持色相；oklch：保持亮度和色相，降低感知色度。
off: disable output gamut compression. cam16ucs (default): CAM16-UCS chroma reduction with the smoothest constant-hue behavior. oklch: perceptual chroma reduction in OkLab, preserves hue + lightness. aces_rgc: per-channel ACES RGC v1.3, matches Resolve/Nuke/OCIO. oklrab/jzazbz: alternative perceptual spaces.|off：关闭输出色域压缩；cam16ucs：默认，平滑保持色相；oklch：保持色相和亮度；aces_rgc：ACES RGC v1.3，与 Resolve/Nuke/OCIO 一致；oklrab/jzazbz：其他感知空间。
CUDA accelerates diffusion and CAM16-UCS in double precision. Other steps use CPU. Missing CUDA or GPU memory falls back to CPU.|CUDA 使用双精度加速柔光和 CAM16-UCS；其他步骤使用 CPU。CUDA 不可用或显存不足时回退到 CPU。
'''.strip().splitlines():
    source, target = line.split('|', 1)
    ZH[source.casefold()] = target
