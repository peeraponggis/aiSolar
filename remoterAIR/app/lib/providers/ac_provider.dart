import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';
import '../models/ac_device.dart';
import '../models/timer_schedule.dart';
import '../services/bridge_service.dart';
import '../services/storage_service.dart';

class AcProvider extends ChangeNotifier {
  List<AcDevice> _devices = [];
  List<TimerSchedule> _timers = [];
  bool _loading = false;
  String? _error;
  Timer? _pollTimer;

  List<AcDevice> get devices => List.unmodifiable(_devices);
  List<TimerSchedule> get timers => List.unmodifiable(_timers);
  bool get loading => _loading;
  String? get error => _error;

  Future<void> init() async {
    _loading = true;
    notifyListeners();
    _devices = await StorageService.loadDevices();
    _timers = await StorageService.loadTimers();
    _loading = false;
    notifyListeners();
    _startPolling();
    _startTimerCheck();
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 30), (_) => _refreshAll());
  }

  void _startTimerCheck() {
    Timer.periodic(const Duration(minutes: 1), (_) => _checkTimers());
  }

  Future<void> _refreshAll() async {
    for (var i = 0; i < _devices.length; i++) {
      final svc = BridgeService(_devices[i].bridgeIp);
      final status = await svc.getStatus();
      _devices[i] = _devices[i].copyWith(
        isConnected: status.online,
        roomTemp: status.roomTemp,
        humidity: status.humidity,
        rssi: status.rssi,
        lastSeen: status.online ? DateTime.now() : _devices[i].lastSeen,
      );
    }
    notifyListeners();
    await StorageService.saveDevices(_devices);
  }

  void _checkTimers() {
    final now = DateTime.now();
    final todayWeekday = now.weekday;
    for (final t in _timers) {
      if (!t.enabled) continue;
      if (!t.weekdays.contains(todayWeekday)) continue;
      if (t.hour == now.hour && t.minute == now.minute) {
        final idx = _devices.indexWhere((d) => d.id == t.deviceId);
        if (idx == -1) continue;
        final dev = _devices[idx];
        _sendSignalForState(
          dev,
          isOn: t.isOn,
          temp: t.targetTemp ?? dev.temperature,
          mode: t.targetMode ?? dev.mode,
        );
      }
    }
  }

  Future<void> addDevice({
    required String name,
    required String location,
    required String bridgeIp,
  }) async {
    final dev = AcDevice(
      id: const Uuid().v4(),
      name: name,
      location: location,
      bridgeIp: bridgeIp,
    );
    _devices.add(dev);
    notifyListeners();
    await StorageService.saveDevices(_devices);
  }

  Future<void> removeDevice(String id) async {
    _devices.removeWhere((d) => d.id == id);
    _timers.removeWhere((t) => t.deviceId == id);
    notifyListeners();
    await StorageService.saveDevices(_devices);
    await StorageService.saveTimers(_timers);
  }

  Future<void> updateDevice(AcDevice device) async {
    final idx = _devices.indexWhere((d) => d.id == device.id);
    if (idx == -1) return;
    _devices[idx] = device;
    notifyListeners();
    await StorageService.saveDevices(_devices);
  }

  Future<bool> saveSignal(String deviceId, String commandName, String signal) async {
    final idx = _devices.indexWhere((d) => d.id == deviceId);
    if (idx == -1) return false;
    final signals = Map<String, String>.from(_devices[idx].signals);
    signals[commandName] = signal;
    _devices[idx] = _devices[idx].copyWith(signals: signals);
    notifyListeners();
    await StorageService.saveDevices(_devices);
    return true;
  }

  Future<bool> togglePower(AcDevice device) async {
    final newState = !device.isOn;
    final key = newState ? 'power_on' : 'power_off';
    final signal = device.signals[key] ?? device.signals['power'];
    if (signal == null) return false;
    final svc = BridgeService(device.bridgeIp);
    final ok = await svc.sendSignal(signal);
    if (ok) {
      final idx = _devices.indexWhere((d) => d.id == device.id);
      if (idx != -1) {
        _devices[idx] = _devices[idx].copyWith(isOn: newState);
        notifyListeners();
        await StorageService.saveDevices(_devices);
      }
    }
    return ok;
  }

  Future<bool> setTemperature(AcDevice device, int temp) async {
    final t = temp.clamp(AcDevice.tempMin, AcDevice.tempMax);
    final key = 'temp_$t';
    final signal = device.signals[key];
    if (signal == null) return false;
    final ok = await BridgeService(device.bridgeIp).sendSignal(signal);
    if (ok) await _updateDeviceField(device.id, temperature: t);
    return ok;
  }

  Future<bool> setMode(AcDevice device, String mode) async {
    final signal = device.signals['mode_$mode'];
    if (signal == null) return false;
    final ok = await BridgeService(device.bridgeIp).sendSignal(signal);
    if (ok) await _updateDeviceField(device.id, mode: mode);
    return ok;
  }

  Future<bool> setFanSpeed(AcDevice device, int speed) async {
    final signal = device.signals['fan_$speed'];
    if (signal == null) return false;
    final ok = await BridgeService(device.bridgeIp).sendSignal(signal);
    if (ok) await _updateDeviceField(device.id, fanSpeed: speed);
    return ok;
  }

  Future<void> _sendSignalForState(AcDevice dev, {required bool isOn, int? temp, String? mode}) async {
    if (isOn) {
      final signal = dev.signals['power_on'] ?? dev.signals['power'];
      if (signal != null) await BridgeService(dev.bridgeIp).sendSignal(signal);
    } else {
      final signal = dev.signals['power_off'] ?? dev.signals['power'];
      if (signal != null) await BridgeService(dev.bridgeIp).sendSignal(signal);
    }
  }

  Future<void> _updateDeviceField(String id, {int? temperature, String? mode, int? fanSpeed}) async {
    final idx = _devices.indexWhere((d) => d.id == id);
    if (idx == -1) return;
    _devices[idx] = _devices[idx].copyWith(
      temperature: temperature,
      mode: mode,
      fanSpeed: fanSpeed,
    );
    notifyListeners();
    await StorageService.saveDevices(_devices);
  }

  Future<void> addTimer(TimerSchedule timer) async {
    _timers.add(timer);
    notifyListeners();
    await StorageService.saveTimers(_timers);
  }

  Future<void> updateTimer(TimerSchedule timer) async {
    final idx = _timers.indexWhere((t) => t.id == timer.id);
    if (idx == -1) return;
    _timers[idx] = timer;
    notifyListeners();
    await StorageService.saveTimers(_timers);
  }

  Future<void> removeTimer(String id) async {
    _timers.removeWhere((t) => t.id == id);
    notifyListeners();
    await StorageService.saveTimers(_timers);
  }

  List<TimerSchedule> timersForDevice(String deviceId) =>
      _timers.where((t) => t.deviceId == deviceId).toList();

  Future<BridgeStatus> pingDevice(AcDevice device) =>
      BridgeService(device.bridgeIp).getStatus();

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }
}
