import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/ac_provider.dart';
import '../services/bridge_service.dart';

class AddDeviceScreen extends StatefulWidget {
  const AddDeviceScreen({super.key});

  @override
  State<AddDeviceScreen> createState() => _AddDeviceScreenState();
}

class _AddDeviceScreenState extends State<AddDeviceScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameCtrl = TextEditingController();
  final _locationCtrl = TextEditingController();
  final _ipCtrl = TextEditingController();
  bool _scanning = false;
  bool _testing = false;
  bool? _testResult;
  List<String> _found = [];

  @override
  void dispose() {
    _nameCtrl.dispose();
    _locationCtrl.dispose();
    _ipCtrl.dispose();
    super.dispose();
  }

  Future<void> _scanNetwork() async {
    setState(() {
      _scanning = true;
      _found = [];
    });
    final found = await BridgeService.discoverBridges();
    setState(() {
      _scanning = false;
      _found = found;
    });
    if (found.isEmpty && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('ไม่พบ IR Bridge ในเครือข่าย')),
      );
    }
  }

  Future<void> _testConnection() async {
    if (_ipCtrl.text.trim().isEmpty) return;
    setState(() {
      _testing = true;
      _testResult = null;
    });
    final svc = BridgeService(_ipCtrl.text.trim());
    final status = await svc.getStatus();
    setState(() {
      _testing = false;
      _testResult = status.online;
    });
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    await context.read<AcProvider>().addDevice(
          name: _nameCtrl.text.trim(),
          location: _locationCtrl.text.trim(),
          bridgeIp: _ipCtrl.text.trim(),
        );
    if (mounted) Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('เพิ่มแอร์ใหม่')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // ข้อมูลแอร์
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('ข้อมูลแอร์', style: Theme.of(context).textTheme.titleSmall),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _nameCtrl,
                      decoration: const InputDecoration(
                        labelText: 'ชื่อแอร์ *',
                        hintText: 'เช่น ห้องนอน, ห้องนั่งเล่น',
                        prefixIcon: Icon(Icons.ac_unit),
                        border: OutlineInputBorder(),
                      ),
                      validator: (v) => (v?.trim().isEmpty ?? true) ? 'กรุณาระบุชื่อ' : null,
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _locationCtrl,
                      decoration: const InputDecoration(
                        labelText: 'ตำแหน่ง (ไม่บังคับ)',
                        hintText: 'เช่น ชั้น 2, โซน A',
                        prefixIcon: Icon(Icons.location_on),
                        border: OutlineInputBorder(),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            // IR Bridge IP
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('IR Bridge', style: Theme.of(context).textTheme.titleSmall),
                    const SizedBox(height: 4),
                    Text(
                      'อุปกรณ์ ESP8266 ที่เชื่อมต่อ WiFi เดียวกัน',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Theme.of(context).colorScheme.outline,
                          ),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: _ipCtrl,
                            decoration: InputDecoration(
                              labelText: 'IP Address *',
                              hintText: '192.168.1.x',
                              prefixIcon: const Icon(Icons.router),
                              border: const OutlineInputBorder(),
                              suffixIcon: _testResult == null
                                  ? null
                                  : Icon(
                                      _testResult! ? Icons.check_circle : Icons.error,
                                      color: _testResult! ? Colors.green : Colors.red,
                                    ),
                            ),
                            keyboardType: TextInputType.number,
                            validator: (v) {
                              if (v?.trim().isEmpty ?? true) return 'กรุณาระบุ IP';
                              return null;
                            },
                          ),
                        ),
                        const SizedBox(width: 8),
                        FilledButton.tonal(
                          onPressed: _testing ? null : _testConnection,
                          child: _testing
                              ? const SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(strokeWidth: 2),
                                )
                              : const Text('ทดสอบ'),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed: _scanning ? null : _scanNetwork,
                      icon: _scanning
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.search),
                      label: Text(_scanning ? 'กำลังสแกน...' : 'สแกนหา Bridge'),
                    ),
                    if (_found.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Text('พบอุปกรณ์:', style: Theme.of(context).textTheme.labelMedium),
                      ..._found.map(
                        (ip) => ListTile(
                          dense: true,
                          leading: const Icon(Icons.router),
                          title: Text(ip),
                          onTap: () => setState(() => _ipCtrl.text = ip),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: _save,
              icon: const Icon(Icons.save),
              label: const Text('บันทึก'),
            ),
          ],
        ),
      ),
    );
  }
}
