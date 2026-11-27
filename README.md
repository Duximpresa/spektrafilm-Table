# spektrafilm-Table

基于 **spektrafilm** 的桌面胶片模拟与照片管理工具。在光谱胶片模拟引擎之上，增加图库、文件夹导航、逐张照片参数保存、中英文界面，以及可选的 NVIDIA CUDA 加速。

## 项目来源与致谢

本项目是 [Andrea Volpato](https://github.com/andreavolpato) 开发的 [spektrafilm](https://github.com/andreavolpato/spektrafilm) 的衍生项目，由 [Duximpresa](https://github.com/Duximpresa) 维护 Table 扩展，**不是上游官方版本**。

- **上游基线**：[3bb2c2d2801ff68b92019cf1dbcbb133d60832bc](https://github.com/andreavolpato/spektrafilm/commit/3bb2c2d2801ff68b92019cf1dbcbb133d60832bc)。本仓库保留上游提交历史。
- **来自上游**：光谱胶片模拟模型、胶片与相纸数据、负片／放大打印／扫描流程、原始 Qt + napari 编辑器、RAW 读取与 LUT 创建工具。
- **Table 扩展**：照片管理工作区、导入选择与缩略图、逐照片编辑状态、交互式白平衡与吸管、输入直方图、预览尺寸、缓存管理、中文界面及 CPU/CUDA 执行后端。

**Film modeling powered by spektrafilm, by Andrea Volpato.**

上游模型的原理、示例和研究背景请参阅[基线版本的上游说明](https://github.com/andreavolpato/spektrafilm/blob/3bb2c2d2801ff68b92019cf1dbcbb133d60832bc/README.md)。原作者的引用信息保留于 [CITATION.cff](CITATION.cff)；Table 的修改记录见 [CHANGES_TABLE.md](CHANGES_TABLE.md)。

## 主要功能

### 图库与照片管理

- 平级的 **图库（Library）／编辑（Develop）** 工作区，共享文件夹导航和底部胶片栏。
- 支持多文件、多文件夹导入，可包含子文件夹；导入前勾选照片、识别重复文件，并可关闭导入缩略图解码。
- 按文件名搜索，按文件夹筛选；记住工作区、文件夹、选中照片和导入位置。
- 胶片栏高度和缩略图大小可调，支持 Ctrl 多选与 Shift 范围选择。
- 每张照片独立保存模拟参数、白平衡、裁剪与旋转；支持复制参数并粘贴到选中的多张照片。
- 原片保留在原位置，不复制、不修改；移除图库条目不会删除原片，移动文件后可重新定位。

### 胶片模拟与编辑

- 使用上游胶片、相纸和扫描模拟流程，调整曝光、颗粒、光晕等效果。
- RAW 默认使用相机白平衡；提供色温、色调滑块及中性灰吸管。滑块基于缓存输入调整，避免每次重新解码 RAW。
- 编辑侧栏显示白平衡调整后的输入 RGB 直方图。
- 图像底部提供预览尺寸选择：Auto、1/1、1/2、1/4、1/8、1/16；**SCAN 始终使用全分辨率**。
- SCAN 显示实际处理阶段、步骤和耗时；对相同输入与参数的成功扫描再次计算前提示确认。
- 支持 JSON 参数预设；简体中文／英文可在设置中切换并记忆，新安装默认简体中文。

### 可选 NVIDIA CUDA 加速

窗口中的 **Compute／计算设备** 可选择 CPU 或 NVIDIA CUDA，选择会保存。CPU 为默认模式，无需 NVIDIA 显卡。

CUDA 使用双精度计算，加速相机扩散、放大机扩散和 CAM16-UCS 输出色域压缩；其余处理仍在 CPU 上执行。设备不可用或显存不足时会显示 CPU 回退状态。首次使用需要初始化和编译内核，实际速度取决于图片尺寸、效果和硬件。

目前仅实现 CPU 与 NVIDIA CUDA，不包含 Metal、Vulkan 或 AMD GPU 后端。详细范围与验证见 [GPU_IMPLEMENTATION.md](GPU_IMPLEMENTATION.md)。

## 安装与启动

以下以 Windows PowerShell 为例，建议使用 **Python 3.13**。项目依赖 Qt、napari、OpenImageIO、rawpy 等组件；本项目的主要验证环境为 Windows。

### 1. 获取项目

先安装 Git 和 [uv](https://docs.astral.sh/uv/)，然后执行：

```powershell
git clone https://github.com/Duximpresa/spektrafilm-Table.git
cd spektrafilm-Table
uv venv --python 3.13 .venv
uv pip install --python .venv/Scripts/python.exe -e .
```

### 2. 启动 Table

安装完成后双击项目根目录的 **Start-Spektrafilm-Table.bat**，或执行：

```powershell
.\.venv\Scripts\python.exe -m spektrafilm_gui.table_app
```

BAT 启动器使用项目内的 `.venv`，不会自动安装依赖。

### 3. 可选：安装 CUDA 后端

需要兼容 CUDA 12 的 NVIDIA 驱动：

```powershell
uv pip install --python .venv/Scripts/python.exe -e ".[cuda]"
```

该额外依赖包含 CuPy 和所需 CUDA 运行时组件，本配置无需单独安装系统级 CUDA Toolkit。安装后重新启动应用，在计算设备中选择 NVIDIA CUDA。

### 其他入口

安装后保留三个入口，Windows 下位于 `.venv/Scripts/`：

| 命令 | 用途 |
| --- | --- |
| `spektrafilm-table` | 本项目的图库与编辑工作区 |
| `spektrafilm` | 上游原始编辑器 |
| `spektrafilm-lut` | 上游 LUT 创建命令行工具 |

Python 包名和导入路径仍沿用 `spektrafilm`，以保持与上游兼容。

## 基本工作流

1. 启动 Table，在图库中导入照片或文件夹，勾选需要加入图库的照片。
2. 双击照片进入编辑工作区，选择胶片与相纸，调整白平衡、曝光和模拟参数。
3. 使用较小的预览尺寸调节效果，需要时通过胶片栏复制、粘贴照片参数。
4. 确认效果后运行 **SCAN**，再使用保存控件导出结果。运行 SCAN 不等同于自动导出文件。

RAW 首次加载需要解码和建立缓存，可能耗时较长。准备外部输入时，应正确匹配输入色彩空间与传递函数设置；高位深、场景线性的 TIFF／EXR 更适合保留模拟所需的信息。

## 数据、缓存与预设

- 图库使用本地 SQLite 数据库，保存原片路径及逐照片编辑参数，不在原片旁写入 sidecar 文件。
- 应用数据默认保存在系统本地应用数据目录下的 `spektrafilm-Table`，Windows 通常为 `%LOCALAPPDATA%/spektrafilm-Table`。备份时请同时保留应用数据和原始照片。
- 设置中的缓存管理支持更换缩略图缓存目录、容量限制和清理；更换目录不会迁移图库数据库，也不会自动删除旧缓存。
- [presets/](presets/README.md) 用于保存 GUI 参数预设；个人预设默认由 Git 忽略。文件对话框会记住成功使用过的位置。
- 文件夹导航只显示已导入的照片，不会自动同步磁盘新增文件。目前使用单一本地图库。

## 当前限制

- 项目仍在持续开发，全分辨率模拟可能耗时较长，CUDA 并未加速全部步骤。
- 支持多照片参数粘贴，但尚未提供批量导出、评级、标签、相册或云同步。
- RAW 色温显示为编辑器拟合的近似值，不保证与相机厂商软件的 Kelvin 数值一致。
- 缩略图代表原始照片，不是所有照片的批量胶片模拟结果。
- 既有验证记录与已知上游数值基线差异见 [VALIDATION_TABLE.md](VALIDATION_TABLE.md)，不代表所有平台、相机与显卡均已验证。

## 开发与测试

```powershell
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest tests -v
```

| 目录 | 内容 |
| --- | --- |
| `src/spektrafilm/` | 上游模拟核心与 Table 执行后端扩展 |
| `src/spektrafilm_gui/` | 原始编辑器、Table 图库与交互界面 |
| `src/spektrafilm_lut_creator/` | 上游 LUT 创建工具 |
| `tests/` | 运行时与 GUI 测试 |
| `scripts/` | 基准测试、界面冒烟检查等辅助工具 |

## 许可证

- **程序代码：GPLv3**，包括 Table 扩展，完整文本见 [LICENSE](LICENSE)。保留上游作者和版权声明。
- **上游胶片配置、LUT 及其直接衍生数据：CC BY-SA 4.0**，原作者为 **Andrea Volpato**，原始来源为 [spektrafilm](https://github.com/andreavolpato/spektrafilm)，完整声明见 [SPEKTRAFILM_LICENSE.txt](SPEKTRAFILM_LICENSE.txt) 及数据目录中的许可证。
- 本项目保留这些许可证与上游引用文件；Table 扩展没有修改上游胶片配置数据。

感谢 Andrea Volpato 和上游贡献者提供光谱模型、数据与工具。若希望支持原作者，可访问其[支持页面](https://buymeacoffee.com/andreavolpato)。
