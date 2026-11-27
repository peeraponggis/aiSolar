import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/ac_provider.dart';
import '../models/ac_device.dart';
import 'scan_screen.dart';
import 'timer_screen.dart';
import 'performance_screen.dart';

class ControlScreen extends StatelessWidget {
  final String deviceId;
  const ControlScreen({super.key, required this.deviceId});

  @override
  Widget build(BuildContext context) {
    return Consumer<AcProvider>(
      builder: (context, provider, _) {
        final device = provider.devices.cast<AcDevice?>().firstWhere(
              (d) => d!.id == deviceId,
              orElse: () => null,
            );
        if (device == null) {
          return const Scaffold(body: Center(child: Text('ไม่พบอุปกรณ์')));
        }
        return _ControlView(device: device);
      },
    );
  }
}

class _ControlView extends StatelessWidget {
  final AcDevice device;
  const _ControlView({required this.device});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: Column(
          children: [
            Text(device.name, style: const TextStyle(fontWeight: FontWeight.bold)),
            if (device.location.isNotEmpty)
              Text(device.location,
                  style: TextStyle(fontSize: 12, color: cs.outline)),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.speed),
            tooltip: 'ประสิทธิภาพ',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                  builder: (_) => PerformanceScreen(deviceId: device.id)),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.timer),
            tooltip: 'ตั้งเวลา',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => TimerScreen(deviceId: device.id)),
            ),
          ),
          PopupMenuButton<String>(
            onSelected: (v) async {
              if (v == 'scan') {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (_) => ScanScreen(deviceId: device.id)),
                );
              } else if (v == 'delete') {
                final ok = await _confirmDelete(context);
                if (ok && context.mounted) {
                  await context.read<AcProvider>().removeDevice(device.id);
                  if (context.mounted) Navigator.pop(context);
                }
              }
            },
            itemBuilder: (_) => [
              const PopupMenuItem(value: 'scan', child: Text('สแกนสัญญาณ IR')),
              const PopupMenuItem(
                  value: 'delete',
                  child: Text('ลบอุปกรณ์', style: TextStyle(color: Colors.red))),
            ],
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _PowerCard(device: device),
          const SizedBox(height: 12),
          _TempCard(device: device),
          const SizedBox(height: 12),
          _ModeCard(device: device),
          const SizedBox(height: 12),
          _FanCard(device: device),
          const SizedBox(height: 12),
          if (device.signals.isEmpty)
            Card(
              color: Theme.of(context).colorScheme.errorContainer,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Icon(Icons.warning_amber, color: cs.error),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('ยังไม่มีสัญญาณ IR',
                              style: TextStyle(
                                  fontWeight: FontWeight.bold, color: cs.error)),
                          Text('กด "สแกนสัญญาณ IR" เพื่อบันทึกคำสั่ง',
                              style: TextStyle(color: cs.onErrorContainer)),
                        ],
                      ),
                    ),
                    TextButton(
                      onPressed: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                            builder: (_) => ScanScreen(deviceId: device.id)),
                      ),
                      child: const Text('สแกน'),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Future<bool> _confirmDelete(BuildContext context) async {
    return await showDialog<bool>(
          context: context,
          builder: (_) => AlertDialog(
            title: const Text('ลบอุปกรณ์'),
            content: Text('ต้องการลบ "${device.name}" ใช่หรือไม่?'),
            actions: [
              TextButton(
                  onPressed: () => Navigator.pop(context, false),
                  child: const Text('ยกเลิก')),
              FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: Colors.red),
                  onPressed: () => Navigator.pop(context, true),
                  child: const Text('ลบ')),
            ],
          ),
        ) ??
        false;
  }
}

class _PowerCard extends StatelessWidget {
  final AcDevice device;
  const _PowerCard({required this.device});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Card(
      color: device.isOn ? cs.primaryContainer : null,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        child: Row(
          children: [
            Icon(Icons.power_settings_new,
                size: 32, color: device.isOn ? cs.primary : cs.outline),
            const SizedBox(width: 16),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('สถานะ', style: Theme.of(context).textTheme.labelMedium),
                Text(
                  device.isOn ? 'เปิดอยู่' : 'ปิดอยู่',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: device.isOn ? cs.primary : cs.outline,
                      ),
                ),
              ],
            ),
            const Spacer(),
            Switch(
              value: device.isOn,
              onChanged: (_) async {
                final ok = await context.read<AcProvider>().togglePower(device);
                if (!ok && context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('ไม่พบสัญญาณ Power')),
                  );
                }
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _TempCard extends StatelessWidget {
  final AcDevice device;
  const _TempCard({required this.device});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.thermostat),
                const SizedBox(width: 8),
                Text('อุณหภูมิ', style: Theme.of(context).textTheme.titleMedium),
                const Spacer(),
                if (device.roomTemp != null)
                  Text(
                    'ห้อง ${device.roomTemp!.toStringAsFixed(1)}°C',
                    style: Theme.of(context)
                        .textTheme
                        .labelMedium
                        ?.copyWith(color: cs.outline),
                  ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton.filled(
                  iconSize: 28,
                  onPressed: device.temperature > AcDevice.tempMin
                      ? () => context
                          .read<AcProvider>()
                          .setTemperature(device, device.temperature - 1)
                      : null,
                  icon: const Icon(Icons.remove),
                ),
                const SizedBox(width: 24),
                Text(
                  '${device.temperature}°C',
                  style: Theme.of(context).textTheme.displaySmall?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: cs.primary,
                      ),
                ),
                const SizedBox(width: 24),
                IconButton.filled(
                  iconSize: 28,
                  onPressed: device.temperature < AcDevice.tempMax
                      ? () => context
                          .read<AcProvider>()
                          .setTemperature(device, device.temperature + 1)
                      : null,
                  icon: const Icon(Icons.add),
                ),
              ],
            ),
            const SizedBox(height: 8),
            SliderTheme(
              data: SliderTheme.of(context).copyWith(trackHeight: 4),
              child: Slider(
                min: AcDevice.tempMin.toDouble(),
                max: AcDevice.tempMax.toDouble(),
                divisions: AcDevice.tempMax - AcDevice.tempMin,
                value: device.temperature.toDouble(),
                label: '${device.temperature}°C',
                onChanged: (v) => context
                    .read<AcProvider>()
                    .setTemperature(device, v.round()),
              ),
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('${AcDevice.tempMin}°C',
                    style: Theme.of(context)
                        .textTheme
                        .labelSmall
                        ?.copyWith(color: cs.outline)),
                Text('${AcDevice.tempMax}°C',
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

class _ModeCard extends StatelessWidget {
  final AcDevice device;
  const _ModeCard({required this.device});

  static const _modeIcons = <String, IconData>{
    'cool': Icons.ac_unit,
    'heat': Icons.wb_sunny,
    'fan': Icons.toys,
    'dry': Icons.water_drop,
    'auto': Icons.autorenew,
  };

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              const Icon(Icons.tune),
              const SizedBox(width: 8),
              Text('โหมด', style: Theme.of(context).textTheme.titleMedium),
            ]),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: AcDevice.modes.map((m) {
                final selected = device.mode == m;
                return ChoiceChip(
                  avatar: Icon(_modeIcons[m], size: 18),
                  label: Text(AcDevice.modeLabels[m] ?? m),
                  selected: selected,
                  selectedColor: cs.primaryContainer,
                  onSelected: (_) =>
                      context.read<AcProvider>().setMode(device, m),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }
}

class _FanCard extends StatelessWidget {
  final AcDevice device;
  const _FanCard({required this.device});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              const Icon(Icons.air),
              const SizedBox(width: 8),
              Text('ความเร็วพัดลม', style: Theme.of(context).textTheme.titleMedium),
            ]),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: AcDevice.fanLabels.entries.map((e) {
                final selected = device.fanSpeed == e.key;
                return GestureDetector(
                  onTap: () =>
                      context.read<AcProvider>().setFanSpeed(device, e.key),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: selected ? cs.primary : cs.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(
                      e.value,
                      style: TextStyle(
                        color: selected ? cs.onPrimary : cs.onSurface,
                        fontWeight:
                            selected ? FontWeight.bold : FontWeight.normal,
                        fontSize: 13,
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }
}
