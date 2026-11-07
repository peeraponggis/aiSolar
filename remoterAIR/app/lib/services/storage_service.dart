import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/ac_device.dart';
import '../models/timer_schedule.dart';

class StorageService {
  static const _devicesKey = 'ac_devices';
  static const _timersKey = 'timers';

  static Future<List<AcDevice>> loadDevices() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_devicesKey);
    if (raw == null) return [];
    try {
      final list = jsonDecode(raw) as List;
      return list.map((e) => AcDevice.fromJson(e as Map<String, dynamic>)).toList();
    } catch (_) {
      return [];
    }
  }

  static Future<void> saveDevices(List<AcDevice> devices) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_devicesKey, jsonEncode(devices.map((d) => d.toJson()).toList()));
  }

  static Future<List<TimerSchedule>> loadTimers() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_timersKey);
    if (raw == null) return [];
    try {
      final list = jsonDecode(raw) as List;
      return list.map((e) => TimerSchedule.fromJson(e as Map<String, dynamic>)).toList();
    } catch (_) {
      return [];
    }
  }

  static Future<void> saveTimers(List<TimerSchedule> timers) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_timersKey, jsonEncode(timers.map((t) => t.toJson()).toList()));
  }
}
