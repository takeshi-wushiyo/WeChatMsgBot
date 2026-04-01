import SwiftUI
import PhotosUI

/// Main screen: pick/take photo, adjust slim slider, generate result.
struct ContentView: View {
    // MARK: - State

    @State private var originalImage: UIImage?
    @State private var resultImage: UIImage?
    @State private var slimPercent: Double = 25
    @State private var isProcessing = false
    @State private var showImagePicker = false
    @State private var showCamera = false
    @State private var showResult = false
    @State private var errorMessage: String?
    @State private var showError = false

    // MARK: - Body

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    headerBanner
                    photoSection
                    sliderSection
                    generateButton
                    Spacer(minLength: 20)
                }
                .padding(.horizontal, 20)
                .padding(.top, 8)
            }
            .navigationTitle("瘦身效果预览")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    if resultImage != nil {
                        Button {
                            showResult = true
                        } label: {
                            Label("查看对比", systemImage: "square.split.2x1")
                        }
                    }
                }
            }
            .sheet(isPresented: $showImagePicker) {
                ImagePicker(image: $originalImage)
            }
            .fullScreenCover(isPresented: $showCamera) {
                CameraView(image: $originalImage)
            }
            .navigationDestination(isPresented: $showResult) {
                if let orig = originalImage, let result = resultImage {
                    ResultView(originalImage: orig, resultImage: result)
                }
            }
            .alert("处理失败", isPresented: $showError, presenting: errorMessage) { _ in
                Button("确定", role: .cancel) {}
            } message: { msg in
                Text(msg)
            }
        }
    }

    // MARK: - Sub-views

    private var headerBanner: some View {
        HStack {
            Image(systemName: "figure.walk")
                .font(.system(size: 32))
                .foregroundStyle(.white)
            VStack(alignment: .leading, spacing: 2) {
                Text("瘦身效果预览")
                    .font(.headline)
                    .foregroundStyle(.white)
                Text("上传或拍摄照片，一键预览瘦身效果")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.85))
            }
            Spacer()
        }
        .padding(16)
        .background(
            LinearGradient(
                colors: [Color(red: 0.23, green: 0.52, blue: 1.0),
                         Color(red: 0.51, green: 0.22, blue: 0.93)],
                startPoint: .leading,
                endPoint: .trailing
            )
        )
        .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var photoSection: some View {
        VStack(spacing: 14) {
            // Preview image or placeholder
            Group {
                if let img = originalImage {
                    Image(uiImage: img)
                        .resizable()
                        .scaledToFit()
                        .frame(maxHeight: 320)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                        .overlay(
                            RoundedRectangle(cornerRadius: 12)
                                .strokeBorder(Color.secondary.opacity(0.3), lineWidth: 1)
                        )
                } else {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color(.secondarySystemBackground))
                        .frame(height: 220)
                        .overlay(
                            VStack(spacing: 8) {
                                Image(systemName: "person.crop.rectangle.badge.plus")
                                    .font(.system(size: 44))
                                    .foregroundStyle(.secondary)
                                Text("请选择或拍摄一张照片")
                                    .font(.subheadline)
                                    .foregroundStyle(.secondary)
                            }
                        )
                }
            }
            .animation(.easeInOut(duration: 0.2), value: originalImage != nil)

            // Photo source buttons
            HStack(spacing: 12) {
                Button {
                    showImagePicker = true
                } label: {
                    Label("相册", systemImage: "photo.on.rectangle")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(Color(red: 0.23, green: 0.52, blue: 1.0))

                Button {
                    showCamera = true
                } label: {
                    Label("拍照", systemImage: "camera")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(Color(red: 0.02, green: 0.84, blue: 0.63))
            }
        }
    }

    private var sliderSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Label("瘦身幅度", systemImage: "slider.horizontal.3")
                    .font(.headline)
                Spacer()
                Text("\(Int(slimPercent))%")
                    .font(.system(.title3, design: .rounded, weight: .bold))
                    .foregroundStyle(Color(red: 0.23, green: 0.52, blue: 1.0))
                    .animation(.none, value: slimPercent)
            }

            Slider(value: $slimPercent, in: 5...50, step: 1)
                .tint(Color(red: 0.23, green: 0.52, blue: 1.0))

            HStack {
                Text("5%（微调）")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Text("50%（大幅瘦身）")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(16)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var generateButton: some View {
        Button {
            generate()
        } label: {
            HStack {
                if isProcessing {
                    ProgressView()
                        .tint(.white)
                        .padding(.trailing, 6)
                    Text("处理中…")
                } else {
                    Image(systemName: "wand.and.stars")
                    Text("生成瘦身效果")
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 4)
        }
        .buttonStyle(.borderedProminent)
        .tint(Color(red: 1.0, green: 0.42, blue: 0.42))
        .controlSize(.large)
        .disabled(originalImage == nil || isProcessing)
    }

    // MARK: - Actions

    private func generate() {
        guard let source = originalImage else { return }
        isProcessing = true
        resultImage = nil

        Task.detached(priority: .userInitiated) {
            let processed = await SlimProcessor.apply(to: source,
                                                      slimPercent: slimPercent)
            await MainActor.run {
                isProcessing = false
                if let processed {
                    resultImage = processed
                    showResult = true
                } else {
                    errorMessage = "图像处理失败，请重试。"
                    showError = true
                }
            }
        }
    }
}

#Preview {
    ContentView()
}
