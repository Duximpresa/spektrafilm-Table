# CPU / NVIDIA CUDA 功能实现

日期：2026-11-12。此文件记录正式源码集成；历史原型实验见 [GPU_UPGRADE_PLAN.md](GPU_UPGRADE_PLAN.md)。

## 使用方法

1. 使用项目的 Python 环境安装可选依赖：`uv pip install --python .venv/Scripts/python.exe -e ".[cuda]"`。
2. 重新启动 `spektrafilm-table`。窗口顶部 **Compute** 可选 **CPU** 或 **NVIDIA CUDA (GPU, float64)**。
3. 选择后执行 Preview 或 SCAN。右侧状态显示真实执行方式，鼠标悬停查看设备名称和完整回退原因。

首次默认 CPU。选择保存在当前图库的应用状态中，不进入照片编辑参数或 JSON 预设。计算期间选择框禁用；任务快照包含后端选择，过期结果不能用于覆盖或导出当前照片。

CUDA 首次实际运算会在工作线程初始化、编译和验证，不会在打开窗口或选择框时阻塞主线程。当前机器已经安装了可选 CUDA 组件；其他安装需要自行安装 `[cuda]`。

## 当前范围

| 内容 | 实现 |
|---|---|
| CPU 后端 | 包装原有函数，旧 `Simulator(params)` 调用保持兼容 |
| NVIDIA CUDA | CuPy / CUDA 12，固定 float64 |
| GPU 算子 | 相机扩散、放大机扩散、CAM16-UCS 输出色域压缩 |
| 其他色域算法 / RAW / 颗粒 / 光晕等 | 原 CPU 实现 |
| Preview 与 SCAN | 都使用所选后端；小图可能因启动/传输成本并不更快 |
| 跨平台显卡 | 已分离后端协议；Metal、Vulkan、ROCm 等尚未实现 |
| 多显卡 | API 可指定 `device_id`；UI 当前使用设备 0 |
| 发布 | 源码及本地环境验证，尚未制作独立 GPU 安装包 |

这是一条 CPU/GPU 混合管线，并非整个 SCAN 在 GPU 上执行。没有引入 float32 默认模式，也没有改变随机颗粒算法。

## 执行接口

```python
from spektrafilm.runtime.api import Simulator, ExecutionOptions

simulator = Simulator(digested_params, execution=ExecutionOptions(backend="cuda"))
try:
    result = simulator.process(image)
    print(simulator.execution_status())
finally:
    simulator.close()
```

源码入口：

- `runtime/execution/__init__.py`：后端描述、不可变执行选项、窄协议与延迟工厂。
- `runtime/execution/cpu.py`：原 CPU 函数适配。
- `runtime/execution/cuda.py`：延迟设备探针、资源作用域、错误分类、CPU 回退与状态。
- `runtime/execution/cuda_kernels.py`：双精度 CAM16 和扩散卷积；包含 colour-science 的 BSD 来源及许可。
- `runtime/pipeline.py` 和三个 stage：显式注入后端；更新照片参数时保留后端对象。
- `spektrafilm_gui/table_controller.py`、`library.py`：选择、保存、工作线程调用、状态反馈与结果过期检查。

以后增加其他平台时，为同一协议增加实现及延迟工厂分支，并在 `BACKENDS` 注册稳定 ID 和显示名称。阶段代码与照片参数不依赖 CUDA；新平台应复用同一套 CPU 数值参考和故障测试。不要把 AMD/Apple 显卡简单重命名成 CUDA，也不要在通用模块顶部导入 GPU 包。

## 数值、内存与回退

- 色域：沿用 CPU Cmax 表和观察条件，主机按行块上传、计算、下载。默认 128 行，显存不足逐次减半到 1 行；仍不足则回退原 CPU 算子。支持 RGB 向量、像素列表和图像。
- 扩散：原 CPU PSF 构造，GPU 每通道完整 FFT 线性卷积；保留 reflect 边界、裁剪和混合。显存不足直接回退，不用缺少重叠区域的分块近似。
- 每个后端有自己的内存池与 stream。初始池上限取 6 GB 与当时可用显存 70% 的较小值；这是池预算，不是包含驱动上下文/FFT 工作区的总显存保证。
- GPU 调用用进程内锁串行化。进入每个调用时显式选择设备/stream/allocator，支持 Qt 把后续任务分配到另一工作线程。计算结束同步后才返回 NumPy 数组。
- 该后端执行期间关闭当前线程的 FFT 计划缓存，随后恢复缓存容量设置。每次请求结束释放自己内存池中的空闲块，不清空其他库的全局内存池、不重置显卡。
- 第一版不跨请求缓存 GPU 图像/PSF/频谱，避免参数失效和无界显存增长；CPU 原有表缓存及 CuPy 编译缓存仍可复用。后续有数据证明收益后再加容量受控的参数缓存。
- 缺依赖、初始化失败、显存不足和 cuFFT/设备错误有明确 CPU 回退提示。设备运行错误后，该后端实例停止后续 GPU 派发；切换 CPU 再切回 CUDA 会重新创建实例。
- 算法 ValueError 等程序错误不会被静默吞掉。实际内核编译错误显示为计算失败；初始化探针失败可以回退。
- 回退只重算当前确定性算子，不重跑随机管线。输入不原地修改。
- 基准用 `ExecutionOptions(backend="cuda", allow_fallback=False)`，可防止依赖/资源故障被当成 GPU 成功。没有 GPU 实现的其他色域算法仍是明确的 CPU 分支。

ProPhoto RGB 极端蓝色测试揭示：参考 CAM16 逆变换遇到 NaN 色相时，其分象限分支保留初始化为零的对立色坐标。正式 CUDA 实现已补齐这一行为；不能仅根据正常 sRGB 样本宣称所有边界等价。

## 依赖与安装边界

`pyproject.toml` 的 `cuda` extra 单独声明 CuPy 14.2、CUDA runtime/NVRTC 12.9、cuFFT 11.4.1 系列。普通安装不要求 CUDA，不修改全局 PATH、`site.getsitepackages` 或实验目录搜索路径。

本机验证 Python 3.13、RTX 3060 12 GB、驱动 610.88，实际 runtime 12090 / NVRTC 12.9。CuPy 在没有系统 Toolkit 路径时可能发出路径检测警告；本次正常组件 wheel 布局下实际数学/FFT 探针成功。以实际探针结果判断可用性。

安装组件 wheel 的方法参考 [CuPy 官方安装说明](https://docs.cupy.dev/en/stable/install.html)。其他 GPU、操作系统和干净打包环境尚未全面验证，不把本机结果当成全平台发布认证。

## 可复现验证

CPU-only CI 默认跳过真实 GPU 测试；显式开启后，缺少 GPU 会失败而不会假装通过：

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
$env:SPEKTRAFILM_TEST_CUDA = '1'
.venv/Scripts/python.exe -m pytest tests/test_execution.py tests/test_scan_progress.py tests/test_runtime_api.py tests/test_pipeline_smoke.py tests/test_filming_stage.py tests/test_topology.py tests/test_gamut_compression.py tests/gui -q
```

覆盖 CPU-only 不导入 CuPy、缺依赖回退/严格模式、参数更新保持后端、三种输出色域及压缩参数、负值/HDR/非连续图像、各扩散滤镜族和奇偶尺寸/边角脉冲、显存不足、程序错误透传、完整直扫/相纸流程、UI 选择持久化与任务状态。

生产后端基准工具为 `scripts/benchmark_execution.py`，不依赖 `.temp` 中的实验函数替换或依赖搜索补丁：

```powershell
.venv/Scripts/python.exe scripts/benchmark_execution.py --image decoded.npy --state state.json --output new-run
```

`--output` 必须是新目录。默认每种后端 4 次（含第一轮），生成计时 JSON、最终数组和全图误差。它要求已有线性解码 NumPy 数组和 GUI 参数 JSON；不含 RAW 解码、GUI 显示与导出时间。固定 NumPy/Numba 种子仅用于测试。完整图像及私人参数不要提交到 Git。

### 本次实测记录

使用相同 `_DSC0304.ARW` 解码缓存、6024 × 4024 像素、相同保存参数与 12 个 Numba 线程，正式 `Simulator` 的严格 CUDA 模式结果如下：

| 后端 | 首轮（秒） | 第二轮（秒） |
|---|---:|---:|
| CPU | 150.69 | 136.74 |
| NVIDIA CUDA float64 + CPU | 76.53 | 60.80 |

本次每种后端只测两轮；第二轮比值约 2.25 倍、耗时缩短约 55.5%，不是三次稳定中位数。CUDA 首轮包含本进程的初始化/编译。测试中 CPU 阶段系统可用内存曾低于 1 GB；不把这次结果和历史原型的 134.32 / 55.08 秒跨批次相除。

固定随机种子的最终全图最大绝对误差 `4.013456234019941e-13`，RMSE `3.243368315753859e-14`，四次输出均有限值，CUDA 两次均没有回退。日志和输出保存在忽略的 `.temp/gpu-integration-20261112/`，包括 `timings.json`、`accuracy.json`、`cpu.npy`、`cuda.npy`。

这一数字只覆盖本机单张真实照片及一套参数；不同预设、尺寸和显卡需要各自测量。


自动化验收：上述命令 **297 passed**（28.84 秒），真实 CUDA 测试全部启用，未跳过。包含 Qt 工作线程实际执行 CUDA → CPU → CUDA 三次 SCAN，GPU 分支确认有真实 GPU 算子调用并生成有限输出；也验证了选择框禁用/恢复和状态设备名称。测试使用独立图库，图库测试的 QSettings 已隔离，避免覆盖用户桌面偏好。

预期警告：没有系统 Toolkit 路径的 CuPy 检测提示，以及极端 ProPhoto 输入在 CPU colour 参考公式中的非有限中间量警告；对应数值回归通过。损坏图片测试还会输出 OpenImageIO 解码错误诊断。这些不等同于 CUDA 运算失败。


界面布局另用 Windows 原生 Qt 平台、独立图库/QSettings/napari 配置检查：实际 Table 窗口成功创建、绘制和关闭，顶部 Compute 选择框可见，CPU 与 NVIDIA CUDA 两项齐全，标题/模块标签/底部胶片条无重叠。截图位于 `.temp/gpu-ui-20261112/compute-selector.png`。最初 offscreen 平台不支持 napari 的 OpenGL 画布，故完整窗口截图改用原生 Windows 渲染；上述自动化 Qt 控件/工作线程测试仍使用 offscreen，不把它们当作 OpenGL 显示性能测试。
