import 'dart:convert';
import 'package:http/http.dart' as http;

class BridgeStatus {
  final bool online;
  final String? ssid;
  final int? rssi;
  final double? roomTemp;
  final double? humidity;
  final String? firmware;
  final int freeHeap;

  const BridgeStatus({
    required this.online,
    this.ssid,
    this.rssi,
    this.roomTemp,
    this.humidity,
    this.firmware,
    this.freeHeap = 0,
  });
}

class LearnResult {
  final bool success;
  final String? signal;
  final String? protocol;
  final int? bits;
  final String? error;

  const LearnResult({
    required this.success,
    this.signal,
    this.protocol,
    this.bits,
    this.error,
  });
}

class BridgeService {
  static const Duration _timeout = Duration(seconds: 5);

  final String ip;

  BridgeService(this.ip);

  String get baseUrl => 'http://$ip';

  Future<BridgeStatus> getStatus() async {
    try {
      final res = await http
          .get(Uri.parse('$baseUrl/api/status'))
          .timeout(_timeout);
      if (res.statusCode == 200) {
        final j = jsonDecode(res.body) as Map<String, dynamic>;
        return BridgeStatus(
          online: true,
          ssid: j['ssid'] as String?,
          rssi: j['rssi'] as int?,
          roomTemp: (j['temp'] as num?)?.toDouble(),
          humidity: (j['hum'] as num?)?.toDouble(),
          firmware: j['firmware'] as String?,
          freeHeap: (j['freeHeap'] as int?) ?? 0,
        );
      }
    } catch (_) {}
    return const BridgeStatus(online: false);
  }

  Future<LearnResult> learnSignal() async {
    try {
      final res = await http
          .post(Uri.parse('$baseUrl/api/learn'))
          .timeout(const Duration(seconds: 15));
      if (res.statusCode == 200) {
        final j = jsonDecode(res.body) as Map<String, dynamic>;
        if (j['success'] == true) {
          return LearnResult(
            success: true,
            signal: j['signal'] as String?,
            protocol: j['protocol'] as String?,
            bits: j['bits'] as int?,
          );
        }
        return LearnResult(success: false, error: j['error'] as String?);
      }
    } catch (e) {
      return LearnResult(success: false, error: e.toString());
    }
    return const LearnResult(success: false, error: 'ไม่ตอบสนอง');
  }

  Future<bool> sendSignal(String signal) async {
    try {
      final res = await http
          .post(
            Uri.parse('$baseUrl/api/send'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'signal': signal}),
          )
          .timeout(_timeout);
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<List<Map<String, dynamic>>> scanWifi() async {
    try {
      final res = await http
          .get(Uri.parse('$baseUrl/api/wifi/scan'))
          .timeout(const Duration(seconds: 12));
      if (res.statusCode == 200) {
        final j = jsonDecode(res.body) as Map<String, dynamic>;
        return List<Map<String, dynamic>>.from(j['networks'] as List? ?? []);
      }
    } catch (_) {}
    return [];
  }

  Future<bool> connectWifi(String ssid, String password) async {
    try {
      final res = await http
          .post(
            Uri.parse('$baseUrl/api/wifi/connect'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'ssid': ssid, 'password': password}),
          )
          .timeout(const Duration(seconds: 10));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  static Future<List<String>> discoverBridges() async {
    final found = <String>[];
    final base = await _getLocalBase();
    if (base == null) return found;

    final futures = List.generate(254, (i) async {
      final ip = '$base.${i + 1}';
      try {
        final res = await http
            .get(Uri.parse('http://$ip/api/status'))
            .timeout(const Duration(milliseconds: 400));
        if (res.statusCode == 200) {
          final j = jsonDecode(res.body) as Map?;
          if (j != null && j.containsKey('firmware')) found.add(ip);
        }
      } catch (_) {}
    });
    await Future.wait(futures);
    return found;
  }

  static Future<String?> _getLocalBase() async {
    return null; // network_info_plus ดูใน provider
  }
}
