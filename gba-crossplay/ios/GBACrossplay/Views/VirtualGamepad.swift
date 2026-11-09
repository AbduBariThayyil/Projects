import SwiftUI

struct VirtualGamepad: View {
    @Binding var keysBitmask: UInt32
    @State private var isTurboActive: Bool = false
    private let haptic = UIImpactFeedbackGenerator(style: .medium)

    var body: some View {
        VStack {
            // Shoulder buttons
            HStack {
                Button(action: {}) {
                    Text("L")
                        .font(.headline)
                        .frame(width: 80, height: 44)
                        .background(Color.white.opacity(0.15))
                        .cornerRadius(12)
                }
                .simultaneousGesture(
                    DragGesture(minimumDistance: 0)
                        .onChanged { _ in setKey(9, down: true) }
                        .onEnded { _ in setKey(9, down: false) }
                )

                Spacer()

                // Turbo Fast-Forward Button
                Button(action: {}) {
                    HStack(spacing: 4) {
                        Image(systemName: "bolt.fill")
                        Text("TURBO")
                    }
                    .font(.caption.bold())
                    .foregroundColor(isTurboActive ? .black : .white)
                    .frame(width: 90, height: 38)
                    .background(isTurboActive ? Color.orange : Color.orange.opacity(0.3))
                    .cornerRadius(19)
                    .overlay(
                        RoundedRectangle(cornerRadius: 19)
                            .stroke(Color.orange, lineWidth: isTurboActive ? 2 : 1)
                    )
                }
                .simultaneousGesture(
                    DragGesture(minimumDistance: 0)
                        .onChanged { _ in
                            if !isTurboActive {
                                isTurboActive = true
                                haptic.impactOccurred()
                                EmulatorBridge.shared().setTurboActive(true)
                            }
                        }
                        .onEnded { _ in
                            isTurboActive = false
                            EmulatorBridge.shared().setTurboActive(false)
                        }
                )

                Spacer()

                Button(action: {}) {
                    Text("R")
                        .font(.headline)
                        .frame(width: 80, height: 44)
                        .background(Color.white.opacity(0.15))
                        .cornerRadius(12)
                }
                .simultaneousGesture(
                    DragGesture(minimumDistance: 0)
                        .onChanged { _ in setKey(8, down: true) }
                        .onEnded { _ in setKey(8, down: false) }
                )
            }
            .padding(.horizontal, 24)

            Spacer()

            // Main Controls: D-Pad and Face Buttons
            HStack(alignment: .bottom) {
                // D-Pad
                ZStack {
                    Circle()
                        .fill(Color.white.opacity(0.08))
                        .frame(width: 150, height: 150)

                    // Up
                    dpadDirection(icon: "arrowtriangle.up.fill", bit: 6)
                        .offset(y: -44)
                    // Down
                    dpadDirection(icon: "arrowtriangle.down.fill", bit: 7)
                        .offset(y: 44)
                    // Left
                    dpadDirection(icon: "arrowtriangle.left.fill", bit: 5)
                        .offset(x: -44)
                    // Right
                    dpadDirection(icon: "arrowtriangle.right.fill", bit: 4)
                        .offset(x: 44)
                }

                Spacer()

                // Start & Select in Middle
                HStack(spacing: 16) {
                    menuPill(name: "SELECT", bit: 2)
                    menuPill(name: "START", bit: 3)
                }
                .padding(.bottom, 20)

                Spacer()

                // A & B Action Buttons
                ZStack {
                    // B Button
                    actionButton(name: "B", bit: 1, color: .red)
                        .offset(x: -36, y: 20)

                    // A Button
                    actionButton(name: "A", bit: 0, color: .blue)
                        .offset(x: 36, y: -20)
                }
                .frame(width: 140, height: 140)
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 24)
        }
    }

    private func setKey(_ bit: Int, down: Bool) {
        if down {
            keysBitmask |= (1 << bit)
        } else {
            keysBitmask &= ~(1 << bit)
        }
        EmulatorBridge.shared().setKeys(keysBitmask)
    }

    private func dpadDirection(icon: String, bit: Int) -> some View {
        Image(systemName: icon)
            .font(.title2)
            .foregroundColor(.white.opacity(0.8))
            .frame(width: 44, height: 44)
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { _ in setKey(bit, down: true) }
                    .onEnded { _ in setKey(bit, down: false) }
            )
    }

    private func actionButton(name: String, bit: Int, color: Color) -> some View {
        Text(name)
            .font(.title.bold())
            .foregroundColor(.white)
            .frame(width: 58, height: 58)
            .background(color.opacity(0.7))
            .clipShape(Circle())
            .shadow(radius: 4)
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { _ in
                        haptic.impactOccurred()
                        setKey(bit, down: true)
                    }
                    .onEnded { _ in setKey(bit, down: false) }
            )
    }

    private func menuPill(name: String, bit: Int) -> some View {
        Text(name)
            .font(.caption2.bold())
            .foregroundColor(.white.opacity(0.7))
            .frame(width: 60, height: 26)
            .background(Color.white.opacity(0.12))
            .cornerRadius(13)
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { _ in setKey(bit, down: true) }
                    .onEnded { _ in setKey(bit, down: false) }
            )
    }
}
