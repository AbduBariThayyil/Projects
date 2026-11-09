import Foundation
import GameController

class GameControllerManager: ObservableObject {
    @Published var isControllerConnected: Bool = false
    @Published var controllerName: String = "None"

    init() {
        setupNotifications()
        checkForConnectedControllers()
    }

    private func setupNotifications() {
        NotificationCenter.default.addObserver(self,
                                               selector: #selector(controllerDidConnect),
                                               name: .GCControllerDidConnect,
                                               object: nil)
        NotificationCenter.default.addObserver(self,
                                               selector: #selector(controllerDidDisconnect),
                                               name: .GCControllerDidDisconnect,
                                               object: nil)
    }

    @objc private func controllerDidConnect(notification: Notification) {
        guard let controller = notification.object as? GCController else { return }
        configure(controller: controller)
    }

    @objc private func controllerDidDisconnect(notification: Notification) {
        checkForConnectedControllers()
    }

    private func checkForConnectedControllers() {
        if let controller = GCController.controllers().first {
            configure(controller: controller)
        } else {
            isControllerConnected = false
            controllerName = "None"
        }
    }

    private func configure(controller: GCController) {
        isControllerConnected = true
        controllerName = controller.vendorName ?? "Gamepad"

        guard let gamepad = controller.extendedGamepad else { return }

        // A Button
        gamepad.buttonA.valueChangedHandler = { _, _, pressed in
            self.setKey(0, down: pressed)
        }
        // B Button
        gamepad.buttonB.valueChangedHandler = { _, _, pressed in
            self.setKey(1, down: pressed)
        }
        // L Shoulder
        gamepad.leftShoulder.valueChangedHandler = { _, _, pressed in
            self.setKey(9, down: pressed)
        }
        // R Shoulder
        gamepad.rightShoulder.valueChangedHandler = { _, _, pressed in
            self.setKey(8, down: pressed)
        }
        // Start & Select
        gamepad.buttonMenu.valueChangedHandler = { _, _, pressed in
            self.setKey(3, down: pressed) // Start
        }
        gamepad.buttonOptions?.valueChangedHandler = { _, _, pressed in
            self.setKey(2, down: pressed) // Select
        }

        // D-Pad
        gamepad.dpad.up.valueChangedHandler = { _, _, pressed in self.setKey(6, down: pressed) }
        gamepad.dpad.down.valueChangedHandler = { _, _, pressed in self.setKey(7, down: pressed) }
        gamepad.dpad.left.valueChangedHandler = { _, _, pressed in self.setKey(5, down: pressed) }
        gamepad.dpad.right.valueChangedHandler = { _, _, pressed in self.setKey(4, down: pressed) }

        // Right Trigger = Fast-Forward / Turbo
        gamepad.rightTrigger.valueChangedHandler = { _, _, pressed in
            EmulatorBridge.shared().setTurboActive(pressed)
        }
    }

    private func setKey(_ bit: Int, down: Bool) {
        var mask: UInt32 = 0
        if down {
            mask |= (1 << bit)
        } else {
            mask &= ~(1 << bit)
        }
        EmulatorBridge.shared().setKeys(mask)
    }
}
