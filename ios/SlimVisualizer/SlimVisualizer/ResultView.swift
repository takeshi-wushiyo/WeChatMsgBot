import SwiftUI
import Photos

/// Side-by-side before/after comparison screen with share and save actions.
struct ResultView: View {
    let originalImage: UIImage
    let resultImage: UIImage

    @State private var shareItem: UIImage?
    @State private var showShareSheet = false
    @State private var savedSuccessfully = false
    @State private var saveError: String?
    @State private var showSaveError = false
    @Environment(\.displayScale) private var displayScale

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                comparisonPanel
                actionRow
                disclaimer
            }
            .padding(16)
        }
        .navigationTitle("对比效果")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    shareComposite()
                } label: {
                    Image(systemName: "square.and.arrow.up")
                }
            }
        }
        .sheet(isPresented: $showShareSheet) {
            if let item = shareItem {
                ShareSheet(items: [item])
            }
        }
        .overlay(alignment: .top) {
            if savedSuccessfully {
                savedBanner
                    .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
        .animation(.spring(duration: 0.4), value: savedSuccessfully)
        .alert("保存失败", isPresented: $showSaveError, presenting: saveError) { _ in
            Button("确定", role: .cancel) {}
        } message: { msg in
            Text(msg)
        }
    }

    // MARK: - Sub-views

    private var comparisonPanel: some View {
        HStack(spacing: 10) {
            imageCard(image: originalImage, label: "原始")
            imageCard(image: resultImage, label: "瘦身后")
        }
    }

    private func imageCard(image: UIImage, label: String) -> some View {
        VStack(spacing: 6) {
            Text(label)
                .font(.caption.bold())
                .foregroundStyle(.secondary)

            Image(uiImage: image)
                .resizable()
                .scaledToFit()
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .strokeBorder(Color.secondary.opacity(0.25), lineWidth: 1)
                )
        }
        .frame(maxWidth: .infinity)
    }

    private var actionRow: some View {
        HStack(spacing: 12) {
            Button {
                saveToPhotos()
            } label: {
                Label("保存到相册", systemImage: "square.and.arrow.down")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(Color(red: 0.51, green: 0.22, blue: 0.93))

            Button {
                shareComposite()
            } label: {
                Label("分享", systemImage: "square.and.arrow.up")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
        }
        .controlSize(.large)
    }

    private var savedBanner: some View {
        HStack(spacing: 8) {
            Image(systemName: "checkmark.circle.fill")
                .foregroundStyle(.green)
            Text("已保存到相册")
                .font(.subheadline.bold())
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
        .background(.regularMaterial)
        .clipShape(Capsule())
        .shadow(radius: 4)
        .padding(.top, 8)
        .onAppear {
            DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) {
                savedSuccessfully = false
            }
        }
    }

    private var disclaimer: some View {
        Text("效果仅供参考与娱乐，基于图像几何变形算法。")
            .font(.caption)
            .foregroundStyle(.secondary)
            .multilineTextAlignment(.center)
            .padding(.bottom, 8)
    }

    // MARK: - Actions

    private func saveToPhotos() {
        PHPhotoLibrary.requestAuthorization(for: .addOnly) { status in
            guard status == .authorized || status == .limited else {
                DispatchQueue.main.async {
                    saveError = "未授权访问相册，请在"设置 > 隐私 > 照片"中允许本应用写入权限。"
                    showSaveError = true
                }
                return
            }
            PHPhotoLibrary.shared().performChanges({
                PHAssetChangeRequest.creationRequestForAsset(from: self.resultImage)
            }) { success, error in
                DispatchQueue.main.async {
                    if success {
                        savedSuccessfully = true
                    } else {
                        saveError = error?.localizedDescription ?? "保存失败，请重试。"
                        showSaveError = true
                    }
                }
            }
        }
    }

    private func shareComposite() {
        let composite = makeCompositeImage()
        shareItem = composite
        showShareSheet = true
    }

    /// Renders a side-by-side composite of original + result for sharing.
    private func makeCompositeImage() -> UIImage {
        let padding: CGFloat = 8
        let labelHeight: CGFloat = 24
        let scale = displayScale
        let imgW = originalImage.size.width
        let imgH = originalImage.size.height
        let totalW = imgW * 2 + padding * 3
        let totalH = imgH + labelHeight + padding * 2

        let renderer = UIGraphicsImageRenderer(
            size: CGSize(width: totalW, height: totalH),
            format: {
                let fmt = UIGraphicsImageRendererFormat()
                fmt.scale = scale
                return fmt
            }()
        )
        return renderer.image { ctx in
            UIColor.systemBackground.setFill()
            ctx.fill(CGRect(x: 0, y: 0, width: totalW, height: totalH))

            // Labels
            let attrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 12, weight: .semibold),
                .foregroundColor: UIColor.secondaryLabel,
            ]
            NSAttributedString(string: "原始", attributes: attrs)
                .draw(at: CGPoint(x: padding, y: padding))
            NSAttributedString(string: "瘦身后", attributes: attrs)
                .draw(at: CGPoint(x: imgW + padding * 2, y: padding))

            // Images
            let y = padding + labelHeight
            originalImage.draw(in: CGRect(x: padding, y: y, width: imgW, height: imgH))
            resultImage.draw(in: CGRect(x: imgW + padding * 2, y: y, width: imgW, height: imgH))
        }
    }
}

// MARK: - UIActivityViewController wrapper

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController,
                                context: Context) {}
}

#Preview {
    NavigationStack {
        ResultView(
            originalImage: UIImage(systemName: "person.fill")!,
            resultImage:   UIImage(systemName: "person.fill")!
        )
    }
}
