import Foundation
import Network
import Combine

struct DiscoveredHost: Identifiable, Hashable {
    let id = UUID()
    let name: String
    let ip: String
    let port: UInt16
    let gameTitle: String
}

class BonjourDiscovery: ObservableObject {
    @Published var hosts: [DiscoveredHost] = []
    @Published var isScanning: Bool = false

    private var udpListener: NWListener?
    private var browser: NWBrowser?

    init() {
        startScanning()
    }

    deinit {
        stopScanning()
    }

    func startScanning() {
        guard !isScanning else { return }
        isScanning = true
        hosts.removeAll()

        startUDPBeaconListener()
        startBonjourBrowser()
    }

    func stopScanning() {
        isScanning = false
        udpListener?.cancel()
        udpListener = nil
        browser?.cancel()
        browser = nil
    }

    private func startUDPBeaconListener() {
        do {
            let params = NWParameters.udp
            params.allowLocalEndpointReuse = true
            let listener = try NWListener(using: params, on: 52840)

            listener.newConnectionHandler = { [weak self] connection in
                connection.start(queue: .main)
                self?.receiveUDP(on: connection)
            }

            listener.start(queue: .main)
            self.udpListener = listener
        } catch {
            print("[BonjourDiscovery] Failed to start UDP listener: \(error)")
        }
    }

    private func receiveUDP(on connection: NWConnection) {
        connection.receiveMessage { [weak self] content, _, _, error in
            if let data = content, let str = String(data: data, encoding: .utf8) {
                self?.parseBeacon(str, from: connection)
            }
            if error == nil {
                self?.receiveUDP(on: connection)
            }
        }
    }

    private func parseBeacon(_ msg: String, from connection: NWConnection) {
        // Expected: "GBALINK:HOST:<hostname>:<game_title>:<tcp_port>"
        let parts = msg.split(separator: ":")
        guard parts.count >= 5, parts[0] == "GBALINK", parts[1] == "HOST" else { return }

        let hostname = String(parts[2])
        let title = String(parts[3])
        guard let port = UInt16(parts[4]) else { return }

        var ip = "127.0.0.1"
        if case let .hostPort(host, _) = connection.endpoint {
            if case let .ipv4(addr) = host {
                ip = "\(addr)"
            }
        }

        let newHost = DiscoveredHost(name: hostname, ip: ip, port: port, gameTitle: title)
        DispatchQueue.main.async {
            if !self.hosts.contains(where: { $0.ip == newHost.ip && $0.port == newHost.port }) {
                self.hosts.append(newHost)
            }
        }
    }

    private func startBonjourBrowser() {
        let descriptor = NWBrowser.Descriptor.bonjour(type: "_gba-link._tcp", domain: "local.")
        let browser = NWBrowser(for: descriptor, using: .tcp)

        browser.browseResultsChangedHandler = { [weak self] results, _ in
            for result in results {
                if case let .service(name, _, _, _) = result.endpoint {
                    print("[BonjourDiscovery] Found Bonjour service: \(name)")
                }
            }
        }

        browser.start(queue: .main)
        self.browser = browser
    }
}
