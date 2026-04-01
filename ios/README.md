# 瘦身效果预览 – iOS App

iOS 版本使用 **Swift 5.9 + SwiftUI**，最低支持 **iOS 16**。

---

## 功能

| 功能 | 说明 |
|---|---|
| 📂 从相册选图 | 使用 `PHPickerViewController`，无需额外权限 |
| 📸 拍摄照片 | 使用原生相机，模拟器自动回退到相册 |
| ⚖️ 瘦身幅度滑块 | 5 % – 50 %，实时显示百分比 |
| ✨ 本地处理 | 基于 `vImage` 的横向收缩 + 轻微锐化，无需联网 |
| 🔄 前后对比视图 | 左原图、右效果图，并排展示 |
| 💾 保存到相册 | `UIImageWriteToSavedPhotosAlbum` |
| 📤 分享 | 合成前后对比图并调用系统分享面板 |

---

## 文件结构

```
ios/SlimVisualizer/
├── SlimVisualizer.xcodeproj/
│   └── project.pbxproj          ← Xcode 工程文件
└── SlimVisualizer/
    ├── SlimVisualizerApp.swift   ← App 入口 (@main)
    ├── ContentView.swift         ← 主界面
    ├── ResultView.swift          ← 前后对比界面
    ├── SlimProcessor.swift       ← 图像处理算法
    ├── ImagePicker.swift         ← 相册选图 (PHPicker)
    ├── CameraView.swift          ← 相机拍照
    ├── Info.plist                ← 权限说明
    └── Assets.xcassets/          ← 图标 & 主色
```

---

## 运行方法

### 方法一：直接打开工程

1. 安装 **Xcode 15** 或更高版本（需要 macOS 13+）。
2. 双击 `ios/SlimVisualizer/SlimVisualizer.xcodeproj` 在 Xcode 中打开。
3. 在 Xcode 中选择目标设备（iOS 模拟器 或 真机）。
4. 将 **Bundle Identifier** 改为自己的（`com.yourname.SlimVisualizer`）。
5. 按 **⌘R** 编译并运行。

### 方法二：命令行编译（Simulator）

```bash
# 查看可用的模拟器
xcrun simctl list devices --json | python3 -m json.tool | grep -A2 "iPhone"

# 编译到模拟器（替换 <UDID> 为上面查到的设备 UDID）
xcodebuild \
  -project ios/SlimVisualizer/SlimVisualizer.xcodeproj \
  -scheme SlimVisualizer \
  -destination "platform=iOS Simulator,id=<UDID>" \
  build
```

---

## 算法说明

`SlimProcessor.swift` 移植自 Python 版 `slim_visualizer.py`，使用完全相同的算法：

```
对 bodyStart(20%) ~ bodyEnd(95%) 高度范围内的每一行：
    t        = 该行在身体区间的归一化位置 [0, 1]
    taper    = sin(t·π)^0.5         ← 平滑过渡曲线
    squeeze  = 1 - slimFactor · taper
    srcX     = cx + (dstX - cx) / squeeze   ← 反向映射
```

最后用 vImage 的 `vImageConvolve_ARGB8888` 做轻微锐化，效果与 Pillow `UnsharpMask` 相当。

---

## 权限

| 权限 | 用途 |
|---|---|
| `NSCameraUsageDescription` | 相机拍照 |
| `NSPhotoLibraryAddUsageDescription` | 保存效果图到相册 |

（PHPicker 选图不需要相册读取权限）

---

## 注意事项

- 效果基于几何变形算法，仅供参考与娱乐。
- 请勿将此工具用于任何可能伤害他人自尊或引起不适的场景。
