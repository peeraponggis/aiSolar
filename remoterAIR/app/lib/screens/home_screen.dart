import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/ac_provider.dart';
import '../models/ac_device.dart';
import 'control_screen.dart';
import 'add_device_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.ac_unit, color: Theme.of(context).colorScheme.primary),
            const SizedBox(width: 8),
            const Text('RemoteAIR', style: TextStyle(fontWeight: FontWeight.bold)),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'รีเฟรช',
            onPressed: () => context.read<AcProvider>().init(),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => const AddDeviceScreen()),
        ),
        icon: const Icon(Icons.add),
        label: const Text('เพิ่มแอร์'),
      ),
      body: Consumer<AcProvider>(
        builder: (context, provider, _) {
          if (provider.loading) {
            return const Center(child: CircularProgressIndicator());
          }
          if (provider.devices.isEmpty) {
            return _EmptyState();
          }
          return ListView.builder(
            padding: const EdgeInsets.only(bottom: 80),
            itemCount: provider.devices.length,
            itemBuilder: (context, i) => _DeviceCard(device: provider.devices[i]),
          );
        },
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.ac_unit, size: 80, color: Theme.of(context).colorScheme.outlineVariant),
          const SizedBox(height: 16),
          Text('ยังไม่มีแอร์', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          Text(
            'กด "เพิ่มแอร์" เพื่อเชื่อมต่อแอร์เครื่องแรก',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.outline,
                ),
          ),
        ],
      ),
    );
  }
}

class _DeviceCard extends StatelessWidget {
  final AcDevice device;

  const _DeviceCard({required this.device});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final isOn = device.isOn;

    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => Navigator.push(
          context,
          MaterialPageRoute(builder: (_) => ControlScreen(deviceId: device.id)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: isOn
                          ? cs.primaryContainer
                          : cs.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      Icons.ac_unit,
                      color: isOn ? cs.primary : cs.outline,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(device.name,
                            style: Theme.of(context)
                                .textTheme
                                .titleMedium
                                ?.copyWith(fontWeight: FontWeight.bold)),
                        if (device.location.isNotEmpty)
                          Text(device.location,
                              style: Theme.of(context)
                                  .textTheme
                                  .bodySmall
                                  ?.copyWith(color: cs.outline)),
                      ],
                    ),
                  ),
                  _PowerButton(device: device),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  _InfoChip(
                    icon: Icons.thermostat,
                    label: '${device.temperature}°C',
                    active: isOn,
                  ),
                  const SizedBox(width: 8),
                  _InfoChip(
                    icon: Icons.air,
                    label: device.modeLabel,
                    active: isOn,
                  ),
                  const SizedBox(width: 8),
                  if (device.roomTemp != null)
                    _InfoChip(
                      icon: Icons.device_thermostat,
                      label: '${device.roomTemp!.toStringAsFixed(1)}°',
                      active: false,
                    ),
                  const Spacer(),
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: device.isConnected ? Colors.green : cs.outline,
                    ),
                  ),
                  const SizedBox(width: 4),
                  Text(
                    device.isConnected ? 'ออนไลน์' : 'ออฟไลน์',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: device.isConnected ? Colors.green : cs.outline,
                        ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PowerButton extends StatelessWidget {
  final AcDevice device;
  const _PowerButton({required this.device});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return IconButton.filled(
      style: IconButton.styleFrom(
        backgroundColor: device.isOn ? cs.primary : cs.surfaceContainerHighest,
        foregroundColor: device.isOn ? cs.onPrimary : cs.outline,
      ),
      icon: const Icon(Icons.power_settings_new),
      onPressed: () async {
        final ok = await context.read<AcProvider>().togglePower(device);
        if (!ok && context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('ไม่พบสัญญาณ Power — กรุณาสแกนก่อน'),
            ),
          );
        }
      },
    );
  }
}

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool active;

  const _InfoChip({required this.icon, required this.label, required this.active});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: active ? cs.primaryContainer.withOpacity(0.5) : cs.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: active ? cs.primary : cs.outline),
          const SizedBox(width: 4),
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: active ? cs.primary : cs.outline,
                ),
          ),
        ],
      ),
    );
  }
}
