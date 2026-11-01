import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/ac_provider.dart';
import '../models/ac_device.dart';
import '../services/bridge_service.dart';

class PerformanceScreen extends StatefulWidget {
  final String deviceId;
  const PerformanceScreen({super.key, required this.deviceId});

  @override
  State<PerformanceScreen> createState() => _PerformanceScreenState();
}

class _PerformanceScreenState extends State<PerformanceScreen> {
  BridgeStatus? _status;
  bool _refreshing = false;
  Timer? _timer;

  AcDevice? _device(AcProvider p) => p.devices.cast<AcDevice?>().firstWhere(
        (d) => d!.id == widget.deviceId,
        orElse: () => null,
      );

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
    _timer = Timer.periodic(const Duration(seconds: 15), (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    final device = _device(context.read<AcProvider>());
    if (device == null) return;
    setState(() => _refreshing = true);
    final s = await BridgeService(device.bridgeIp).getStatus();
    setState(() {
      _status = s;
      _refreshing = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AcProvider>(builder: (context, provider, _) {
      final device = _device(provider);
      if (device == null) return const Scaffold(body: Center(child: Text('ไม่พบอุปกรณ์')));
      return Scaffold(
        appBar: AppBar(
          title: Text('ประสิทธิภาพ — ${device.name}'),
          actions: [
            if (_refreshing)
              const Padding(
                padding: EdgeInsets.all(14),
                child: SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)),
              )
            else
              IconButton(icon: const Icon(Icons.refresh), onPressed: _refresh),
          ],
        ),
        body: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _StatusRow(device: device, status: _status),
            const SizedBox(height: 12),
            _ParameterGrid(device: device, status: _status),
            const SizedBox(height: 12),
            _BridgeInfo(status: _status),
            const SizedBox(height: 12),
            _EnergyCard(device: device),
            const SizedBox(height: 12),
            _SignalInventory(device: device),
          ],
        ),
      );
    });
  }
}

class _StatusRow extends StatelessWidget {
  final AcDevice device;
  final BridgeStatus? status;
  const _StatusRow({required this.device, required this.status});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final online = status?.online ?? device.isConnected;
    return Card(
      color: online ? cs.primaryContainer : cs.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(online ? Icons.wifi : Icons.wifi_off,
                color: online ? cs.primary : cs.error, size: 32),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(online ? 'IR Bridge ออนไลน์' : 'Bridge ออฟไลน์',
                    style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: online ? cs.primary : cs.error)),
                Text('IP: ${device.bridgeIp}',
                    style: Theme.of(context)
                        .textTheme
                        .bodySmall
                        ?.copyWith(color: cs.outline)),
              ],
            ),
            const Spacer(),
            if (status?.rssi != null)
              _RssiIcon(rssi: status!.rssi!),
          ],
        ),
      ),
    );
  }
}

class _RssiIcon extends StatelessWidget {
  final int rssi;
  const _RssiIcon({required this.rssi});

  @override
  Widget build(BuildContext context) {
    final bars = rssi > -60 ? 4 : rssi > -70 ? 3 : rssi > -80 ? 2 : 1;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.signal_wifi_4_bar, size: 24,
            color: bars >= 3 ? Colors.green : bars == 2 ? Colors.orange : Colors.red),
        Text('$rssi dBm',
            style: Theme.of(context).textTheme.labelSmall),
      ],
    );
  }
}

class _ParameterGrid extends StatelessWidget {
  final AcDevice device;
  final BridgeStatus? status;
  const _ParameterGrid({required this.device, required this.status});

  @override
  Widget build(BuildContext context) {
    final roomT = status?.roomTemp ?? device.roomTemp;
    final hum = status?.humidity ?? device.humidity;
    final items = [
      _Param('สถานะ', device.isOn ? 'เปิด' : 'ปิด',
          device.isOn ? Icons.power_settings_new : Icons.power_off,
          color: device.isOn ? Colors.green : Colors.grey),
      _Param('อุณหภูมิตั้ง', '${device.temperature}°C', Icons.thermostat),
      _Param('โหมด', device.modeLabel, Icons.tune),
      _Param('ความเร็วพัดลม', device.fanLabel, Icons.air),
      if (roomT != null) _Param('ห้อง', '${roomT.toStringAsFixed(1)}°C', Icons.device_thermostat),
      if (hum != null) _Param('ความชื้น', '${hum.toStringAsFixed(0)}%', Icons.water_drop),
      _Param('สัญญาณที่บันทึก', '${device.signals.length} คำสั่ง', Icons.sensors),
    ];
    return GridView.count(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      crossAxisSpacing: 8,
      mainAxisSpacing: 8,
      childAspectRatio: 1.6,
      children: items.map((p) => _ParamCard(param: p)).toList(),
    );
  }
}

class _Param {
  final String label;
  final String value;
  final IconData icon;
  final Color? color;
  const _Param(this.label, this.value, this.icon, {this.color});
}

class _ParamCard extends StatelessWidget {
  final _Param param;
  const _ParamCard({required this.param});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final color = param.color ?? cs.primary;
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Icon(param.icon, size: 20, color: color),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(param.value,
                    style: Theme.of(context)
                        .textTheme
                        .titleMedium
                        ?.copyWith(fontWeight: FontWeight.bold, color: color)),
                Text(param.label,
                    style: Theme.of(context)
                        .textTheme
                        .labelSmall
                        ?.copyWith(color: cs.outline)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _BridgeInfo extends StatelessWidget {
  final BridgeStatus? status;
  const _BridgeInfo({required this.status});

  @override
  Widget build(BuildContext context) {
    if (status == null || !status!.online) return const SizedBox.shrink();
    final cs = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('ข้อมูล IR Bridge', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            _Row('WiFi', status!.ssid ?? '-'),
            _Row('Firmware', status!.firmware ?? '-'),
            _Row('Free Heap', '${status!.freeHeap} bytes'),
          ],
        ),
      ),
    );
  }
}

class _Row extends StatelessWidget {
  final String label;
  final String value;
  const _Row(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          SizedBox(
            width: 100,
            child: Text(label,
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: Theme.of(context).colorScheme.outline)),
          ),
          Text(value, style: Theme.of(context).textTheme.bodyMedium),
        ],
      ),
    );
  }
}

class _EnergyCard extends StatelessWidget {
  final AcDevice device;
  const _EnergyCard({required this.device});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final watts = device.estimatedWatts;
    final kwhPerDay = watts * 8 / 1000;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              const Icon(Icons.bolt),
              const SizedBox(width: 8),
              Text('พลังงานโดยประมาณ', style: Theme.of(context).textTheme.titleSmall),
            ]),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _EnergyItem('${watts.toStringAsFixed(0)} W', 'กำลังปัจจุบัน', cs.primary),
                _EnergyItem('${kwhPerDay.toStringAsFixed(2)} kWh', 'ต่อวัน (8 ชม.)', cs.secondary),
                _EnergyItem('${(kwhPerDay * 30 * 5).toStringAsFixed(0)} ฿', 'ค่าไฟ/เดือน', cs.tertiary),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              '* คำนวณจากประมาณการ ไม่ใช่การวัดจริง',
              style: Theme.of(context)
                  .textTheme
                  .labelSmall
                  ?.copyWith(color: cs.outline),
            ),
          ],
        ),
      ),
    );
  }
}

class _EnergyItem extends StatelessWidget {
  final String value;
  final String label;
  final Color color;
  const _EnergyItem(this.value, this.label, this.color);

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(value,
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.bold, color: color)),
        Text(label,
            style: Theme.of(context)
                .textTheme
                .labelSmall
                ?.copyWith(color: Theme.of(context).colorScheme.outline)),
      ],
    );
  }
}

class _SignalInventory extends StatelessWidget {
  final AcDevice device;
  const _SignalInventory({required this.device});

  @override
  Widget build(BuildContext context) {
    if (device.signals.isEmpty) return const SizedBox.shrink();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('สัญญาณที่บันทึกไว้', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: device.signals.keys.map((k) => Chip(
                    label: Text(k, style: const TextStyle(fontSize: 11)),
                    avatar: const Icon(Icons.sensors, size: 14),
                    visualDensity: VisualDensity.compact,
                  )).toList(),
            ),
          ],
        ),
      ),
    );
  }
}
