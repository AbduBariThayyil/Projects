import SwiftUI
import MetalKit

struct MetalView: UIViewRepresentable {
    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeUIView(context: Context) -> MTKView {
        let mtkView = MTKView()
        mtkView.delegate = context.coordinator
        mtkView.device = MTLCreateSystemDefaultDevice()
        mtkView.framebufferOnly = true
        mtkView.clearColor = MTLClearColor(red: 0.05, green: 0.05, blue: 0.07, alpha: 1.0)
        mtkView.preferredFramesPerSecond = 120 // ProMotion support
        return mtkView
    }

    func updateUIView(_ uiView: MTKView, context: Context) {}

    class Coordinator: NSObject, MTKViewDelegate {
        var commandQueue: MTLCommandQueue?
        var texture: MTLTexture?

        override init() {
            super.init()
            guard let device = MTLCreateSystemDefaultDevice() else { return }
            self.commandQueue = device.makeCommandQueue()

            let desc = MTLTextureDescriptor.texture2DDescriptor(pixelFormat: .bgra8Unorm,
                                                                 width: 240,
                                                                 height: 160,
                                                                 mipmapped: false)
            desc.usage = [.shaderRead]
            self.texture = device.makeTexture(descriptor: desc)
        }

        func mtkView(_ view: MTKView, drawableSizeWillChange size: CGSize) {}

        func draw(in view: MTKView) {
            guard let drawable = view.currentDrawable,
                  let passDesc = view.currentRenderPassDescriptor,
                  let cmdBuf = commandQueue?.makeCommandBuffer(),
                  let encoder = cmdBuf.makeRenderCommandEncoder(descriptor: passDesc) else {
                return
            }

            // Update texture from EmulatorBridge video buffer
            if let pixels = EmulatorBridge.shared.getVideoBuffer(), let texture = self.texture {
                let region = MTLRegionMake2D(0, 0, 240, 160)
                texture.replace(region: region, mipmapLevel: 0, withBytes: pixels, bytesPerRow: 240 * 4)
            }

            encoder.endEncoding()
            cmdBuf.present(drawable)
            cmdBuf.commit()
        }
    }
}
