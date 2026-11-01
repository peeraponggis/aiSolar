import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../providers/ac_provider.dart';
import '../models/ac_device.dart';
import '../services/bridge_service.dart';

const _presetCommands = [
  'power_on',
  'power_off',
  'power',
  'temp_16', 'temp_17', 'temp_18', 'temp_19', 'temp_20',
  'temp_21', 'temp_22', 'temp_23', 'temp_24', 'temp_25',
  'temp_26', 'temp_27', 'temp_28', 'temp_29', 'temp_30',
  'mode_cool', 'mode_heat', 'mode_fan', 'mode_dry', 'mode_auto',
  'fan_0', 'fan_1', 'fan_2', 'fan_3', 'fan_4',
];

const _commandLabels = <String, String>{
  'power_on': 'เปิดเครื่อง',
  'power_off': 'ปิดเครื่อง',
  'power': 'Toggle เปิด/ปิด',
  'mode_cool': 'โหมดทำเย็น',
  'mode_heat': 'โหมดทำร้อน',
  'mode_fan': 'โหมดพัดลม',
  'mode_dry': 'โหมดลดความชื้น',
  'mode_auto': 'โหมดอัตโนมัติ',
  'fan_0': 'พัดลม Auto',
  'fan_1': 'พัดลมเบา',
  'fan_2': 'พัดลมกลาง',
  'fan_3': 'พัดลมแรง',
  'fan_4': 'พัดลมสูงสุด',
};

class ScanScreen extends StatefulWidget {
  final String deviceId;
  const ScanScreen({super.key, required this.deviceId});

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  String? _selectedCommand;
  final _customCtrl = TextEditingController(text: '');
  bool _learning = false;
  String? _lastSignal;
  String? _lastProtocol;
  String? _error;

  AcDevice? _device(AcProvider p) =>
      p.devices.cast<AcDevice?>().firstWhere(
            (d) => d!.id == widget.deviceId,
            orElse: () => null,
          );

  Future<void> _learn(AcProvider provider) async {
    final device = _device(provider);
    if (device == null) return;
    final cmd = _selectedCommand == '_custom' ? _customCtrl.text.trim() : _selectedCommand;
    if (cmd == null || cmd.isEmpty) {
      setState(() => _error = 'กรุณาเลือกคำสั่ง');
      return;
    }
    setState(() {
      _learning = true;
      _lastSignal = null;
      _error = null;
    });
    final svc = BridgeService(device.bridgeIp);
    final result = await svc.learnSignal();
    setState(() => _learning = false);
    if (!result.success) {
      setState(() => _error = result.error ?? 'ไม่ได้รับสัญญาณ');
      return;
    }
    setState(() {
      _lastSignal = result.signal;
      _lastProtocol = result.protocol;
    });
    await provider.saveSignal(device.id, cmd, result.signal!);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('บันทึก "$cmd" สำเร็จ')),
      );
    }
  }

  @override
  void dispose() {
    _customCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Consumer<AcProvider>(builder: (context, provider, _) {
      final device = _device(provider);
      if (device == null) return const Scaffold(body: Center(child: Text('ไม่พบอุปกรณ์')));
      final savedSignals = device.signals;

      return Scaffold(
        appBar: AppBar(title: Text('สแกน IR — ${device.name}')),
        body: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              color: cs.primaryContainer,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    const Icon(Icons.sensors, size: 48),
                    const SizedBox(height: 8),
                    Text(
                      'ชี้รีโมทไปที่ IR Bridge แล้วกดปุ่มบนรีโมทจริง',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            // เลือกคำสั่ง
            Text('คำสั่ง:', style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                ..._presetCommands.map((cmd) {
                  final label = _commandLabels[cmd] ?? cmd;
                  final hasSig = savedSignals.containsKey(cmd);
                  return FilterChip(
                    label: Text(label),
                    selected: _selectedCommand == cmd,
                    avatar: hasSig ? const Icon(Icons.check, size: 14) : null,
                    selectedColor: cs.primaryContainer,
                    onSelected: (_) => setState(() => _selectedCommand = cmd),
                  );
                }),
                FilterChip(
                  label: const Text('กำหนดเอง'),
                  selected: _selectedCommand == '_custom',
                  selectedColor: cs.secondaryContainer,
                  onSelected: (_) => setState(() => _selectedCommand = '_custom'),
                ),
              ],
            ),
            if (_selectedCommand == '_custom') ...[
              const SizedBox(height: 8),
              TextField(
                controller: _customCtrl,
                decoration: const InputDecoration(
                  labelText: 'ชื่อคำสั่ง',
                  hintText: 'เช่น swing_on',
                  border: OutlineInputBorder(),
                ),
              ),
            ],
            const SizedBox(height: 16),
            if (_error != null)
              Card(
                color: cs.errorContainer,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: [
                      Icon(Icons.error_outline, color: cs.error),
                      const SizedBox(width: 8),
                      Expanded(child: Text(_error!, style: TextStyle(color: cs.onErrorContainer))),
                    ],
                  ),
                ),
              ),
            if (_lastSignal != null) ...[
              Card(
                color: cs.secondaryContainer,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(Icons.check_circle, color: cs.secondary),
                          const SizedBox(width: 8),
                          Text('บันทึกสำเร็จ!',
                              style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  color: cs.onSecondaryContainer)),
                        ],
                      ),
                      if (_lastProtocol != null) ...[
                        const SizedBox(height: 4),
                        Text('Protocol: $_lastProtocol',
                            style: Theme.of(context)
                                .textTheme
                                .bodySmall
                                ?.copyWith(color: cs.outline)),
                      ],
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              _lastSignal!.length > 40
                                  ? '${_lastSignal!.substring(0, 40)}…'
                                  : _lastSignal!,
                              style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
                            ),
                          ),
                          IconButton(
                            icon: const Icon(Icons.copy, size: 18),
                            onPressed: () =>
                                Clipboard.setData(ClipboardData(text: _lastSignal!)),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
            const SizedBox(height: 16),
            SizedBox(
              height: 56,
              child: FilledButton.icon(
                onPressed: _learning ? null : () => _learn(provider),
                icon: _learning
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.sensors),
                label: Text(_learning ? 'รอสัญญาณ... กดปุ่มบนรีโมท' : 'เริ่มสแกน'),
              ),
            ),
            const SizedBox(height: 24),
            if (savedSignals.isNotEmpty) ...[
              Text('สัญญาณที่บันทึกไว้ (${savedSignals.length})',
                  style: Theme.of(context).textTheme.titleSmall),
              const SizedBox(height: 8),
              ...savedSignals.entries.map((e) => ListTile(
                    dense: true,
                    leading: const Icon(Icons.wifi_tethering),
                    title: Text(_commandLabels[e.key] ?? e.key),
                    subtitle: Text(
                      e.value.length > 30 ? '${e.value.substring(0, 30)}…' : e.value,
                      style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
                    ),
                    trailing: IconButton(
                      icon: const Icon(Icons.delete_outline, size: 18),
                      color: cs.error,
                      onPressed: () async {
                        final signals = Map<String, String>.from(device.signals)
                          ..remove(e.key);
                        await provider.saveSignal(device.id, '__delete__', '');
                        final updated = device.copyWith(signals: signals);
                        await provider.updateDevice(updated);
                      },
                    ),
                  )),
            ],
          ],
        ),
      );
    });
  }
}
