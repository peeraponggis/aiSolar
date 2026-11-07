import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:uuid/uuid.dart';
import '../providers/ac_provider.dart';
import '../models/timer_schedule.dart';
import '../models/ac_device.dart';

class TimerScreen extends StatelessWidget {
  final String deviceId;
  const TimerScreen({super.key, required this.deviceId});

  @override
  Widget build(BuildContext context) {
    return Consumer<AcProvider>(builder: (context, provider, _) {
      final timers = provider.timersForDevice(deviceId);
      final device = provider.devices.cast<AcDevice?>().firstWhere(
            (d) => d!.id == deviceId,
            orElse: () => null,
          );
      return Scaffold(
        appBar: AppBar(title: Text('ตั้งเวลา — ${device?.name ?? ""}')),
        floatingActionButton: FloatingActionButton(
          onPressed: () => _showAddDialog(context, deviceId),
          child: const Icon(Icons.add),
        ),
        body: timers.isEmpty
            ? const Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.timer_off, size: 64, color: Colors.grey),
                    SizedBox(height: 12),
                    Text('ยังไม่มีตารางเวลา'),
                  ],
                ),
              )
            : ListView.builder(
                padding: const EdgeInsets.only(bottom: 80),
                itemCount: timers.length,
                itemBuilder: (context, i) => _TimerCard(timer: timers[i]),
              ),
      );
    });
  }

  void _showAddDialog(BuildContext context, String deviceId) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (_) => _TimerForm(deviceId: deviceId),
    );
  }
}

class _TimerCard extends StatelessWidget {
  final TimerSchedule timer;
  const _TimerCard({required this.timer});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Card(
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor:
              timer.isOn ? cs.primaryContainer : cs.surfaceContainerHighest,
          child: Icon(
            timer.isOn ? Icons.power_settings_new : Icons.power_off,
            color: timer.isOn ? cs.primary : cs.outline,
          ),
        ),
        title: Text(
          timer.timeText,
          style: Theme.of(context)
              .textTheme
              .titleLarge
              ?.copyWith(fontWeight: FontWeight.bold),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(timer.isOn ? 'เปิดเครื่อง' : 'ปิดเครื่อง'),
            Text(timer.weekdayText,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(color: cs.outline)),
            if (timer.targetTemp != null)
              Text('${timer.targetTemp}°C · ${timer.targetMode ?? ''}',
                  style: Theme.of(context).textTheme.labelSmall),
          ],
        ),
        isThreeLine: true,
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Switch(
              value: timer.enabled,
              onChanged: (v) => context.read<AcProvider>().updateTimer(timer.copyWith(enabled: v)),
            ),
            IconButton(
              icon: const Icon(Icons.delete_outline),
              color: cs.error,
              onPressed: () => context.read<AcProvider>().removeTimer(timer.id),
            ),
          ],
        ),
      ),
    );
  }
}

class _TimerForm extends StatefulWidget {
  final String deviceId;
  const _TimerForm({required this.deviceId});

  @override
  State<_TimerForm> createState() => _TimerFormState();
}

class _TimerFormState extends State<_TimerForm> {
  bool _isOn = true;
  int _hour = TimeOfDay.now().hour;
  int _minute = TimeOfDay.now().minute;
  List<int> _weekdays = [1, 2, 3, 4, 5];
  int? _targetTemp;
  String? _targetMode;

  Future<void> _pickTime() async {
    final t = await showTimePicker(
      context: context,
      initialTime: TimeOfDay(hour: _hour, minute: _minute),
    );
    if (t != null) setState(() {
      _hour = t.hour;
      _minute = t.minute;
    });
  }

  void _save() {
    final timer = TimerSchedule(
      id: const Uuid().v4(),
      deviceId: widget.deviceId,
      isOn: _isOn,
      hour: _hour,
      minute: _minute,
      weekdays: List.from(_weekdays),
      targetTemp: _targetTemp,
      targetMode: _targetMode,
    );
    context.read<AcProvider>().addTimer(timer);
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom + 16,
        left: 16, right: 16, top: 24,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('เพิ่มตั้งเวลา', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: GestureDetector(
                  onTap: _pickTime,
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: cs.primaryContainer,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Column(
                      children: [
                        Text('เวลา',
                            style: Theme.of(context).textTheme.labelMedium),
                        Text(
                          '${_hour.toString().padLeft(2,'0')}:${_minute.toString().padLeft(2,'0')}',
                          style: Theme.of(context).textTheme.displaySmall?.copyWith(
                                fontWeight: FontWeight.bold,
                                color: cs.primary,
                              ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Column(
                children: [
                  Text('การทำงาน', style: Theme.of(context).textTheme.labelMedium),
                  const SizedBox(height: 8),
                  SegmentedButton<bool>(
                    segments: const [
                      ButtonSegment(value: true, label: Text('เปิด'), icon: Icon(Icons.power_settings_new)),
                      ButtonSegment(value: false, label: Text('ปิด'), icon: Icon(Icons.power_off)),
                    ],
                    selected: {_isOn},
                    onSelectionChanged: (s) => setState(() => _isOn = s.first),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text('วัน:', style: Theme.of(context).textTheme.labelMedium),
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            children: List.generate(7, (i) {
              final day = i + 1;
              final label = TimerSchedule.dayLabels[day];
              final selected = _weekdays.contains(day);
              return FilterChip(
                label: Text(label),
                selected: selected,
                onSelected: (v) {
                  setState(() {
                    if (v) _weekdays.add(day);
                    else _weekdays.remove(day);
                  });
                },
              );
            }),
          ),
          if (_isOn) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<int>(
                    decoration: const InputDecoration(
                        labelText: 'อุณหภูมิ (ไม่บังคับ)', border: OutlineInputBorder()),
                    value: _targetTemp,
                    items: List.generate(AcDevice.tempMax - AcDevice.tempMin + 1, (i) {
                      final t = AcDevice.tempMin + i;
                      return DropdownMenuItem(value: t, child: Text('$t°C'));
                    }),
                    onChanged: (v) => setState(() => _targetTemp = v),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: DropdownButtonFormField<String>(
                    decoration: const InputDecoration(
                        labelText: 'โหมด (ไม่บังคับ)', border: OutlineInputBorder()),
                    value: _targetMode,
                    items: AcDevice.modes.map((m) => DropdownMenuItem(
                          value: m,
                          child: Text(AcDevice.modeLabels[m] ?? m),
                        )).toList(),
                    onChanged: (v) => setState(() => _targetMode = v),
                  ),
                ),
              ],
            ),
          ],
          const SizedBox(height: 16),
          FilledButton(onPressed: _save, child: const Text('บันทึก')),
          const SizedBox(height: 8),
        ],
      ),
    );
  }
}
