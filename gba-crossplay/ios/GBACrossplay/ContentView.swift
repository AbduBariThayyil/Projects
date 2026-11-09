import SwiftUI

struct ContentView: View {
    @StateObject private var discovery = BonjourDiscovery()
    @StateObject private var controllerManager = GameControllerManager()
    @State private var keysBitmask: UInt32 = 0
    @State private var isShowingLobby: Bool = false
    @State private var manualIP: String = ""
    @State private var isConnected: Bool = false
    @State private var connectedHostName: String = "Offline"
    @State private var isTurboBadge: Bool = false

    var body: some View {
        ZStack {
            Color(red: 0.07, green: 0.07, blue: 0.09).ignoresSafeArea()

            VStack(spacing: 8) {
                // Top Bar
                HStack {
                    // Connection Status Pill
                    Button(action: { isShowingLobby = true }) {
                        HStack(spacing: 6) {
                            Circle()
                                .fill(isConnected ? Color.green : Color.yellow)
                                .frame(width: 8, height: 8)
                            Text(isConnected ? connectedHostName : "Lobby (Scan)")
                                .font(.caption.bold())
                                .foregroundColor(.white)
                        }
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .background(Color.white.opacity(0.1))
                        .cornerRadius(12)
                    }

                    Spacer()

                    if isTurboBadge {
                        Text("TURBO ACTIVE")
                            .font(.caption2.bold())
                            .foregroundColor(.black)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 3)
                            .background(Color.orange)
                            .cornerRadius(8)
                    }

                    if controllerManager.isControllerConnected {
                        Image(systemName: "gamecontroller.fill")
                            .foregroundColor(.green)
                            .font(.subheadline)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 4)

                // GBA Video Viewport (Metal)
                ZStack {
                    Color.black
                    MetalView()
                        .aspectRatio(1.5, contentMode: .fit) // 240x160 GBA ratio
                }
                .frame(maxWidth: .infinity)
                .frame(maxHeight: 280)
                .cornerRadius(12)
                .padding(.horizontal, 8)

                // Virtual On-Screen Gamepad
                VirtualGamepad(keysBitmask: $keysBitmask)
            }
        }
        .sheet(isPresented: $isShowingLobby) {
            lobbySheet
        }
        .onAppear {
            discovery.startScanning()
        }
    }

    private var lobbySheet: some View {
        NavigationView {
            List {
                Section(header: Text("Nearby Arch Linux Hosts")) {
                    if discovery.hosts.isEmpty {
                        HStack {
                            ProgressView()
                                .padding(.trailing, 8)
                            Text("Searching Wi-Fi for GBA Hosts...")
                                .foregroundColor(.secondary)
                        }
                    } else {
                        ForEach(discovery.hosts) { host in
                            HStack {
                                VStack(alignment: .leading) {
                                    Text(host.name)
                                        .font(.headline)
                                    Text("\(host.gameTitle) • \(host.ip):\(host.port)")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                                Spacer()
                                Button("Join") {
                                    connect(to: host.ip, port: host.port, name: host.name)
                                }
                                .buttonStyle(.borderedProminent)
                            }
                        }
                    }
                }

                Section(header: Text("Manual Connect")) {
                    HStack {
                        TextField("Host IP (e.g. 192.168.1.15)", text: $manualIP)
                            .keyboardType(.numbersAndPunctuation)
                        Button("Connect") {
                            connect(to: manualIP, port: 52841, name: "Arch Linux")
                        }
                        .disabled(manualIP.isEmpty)
                    }
                }
            }
            .navigationTitle("Multiplayer Lobby")
            .navigationBarItems(trailing: Button("Done") { isShowingLobby = false })
        }
    }

    private func connect(to ip: String, port: UInt16, name: String) {
        if EmulatorBridge.shared().connect(toHost: ip, port: port) {
            isConnected = true
            connectedHostName = name
            isShowingLobby = false
        }
    }
}
