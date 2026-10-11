import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/theme.dart';
import '../providers/app_provider.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';
import '../widgets/qr_dialog.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _serverUrlController = TextEditingController();
  double _workers = 16;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    _serverUrlController.text = apiService.baseUrl;
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    final settings = await apiService.getSettings();
    if (settings != null && mounted) {
      setState(() {
        _workers = (settings['parallel_workers'] as num?)?.toDouble() ?? 16;
      });
    }
  }

  @override
  void dispose() {
    _serverUrlController.dispose();
    super.dispose();
  }

  Future<void> _saveSettings() async {
    setState(() => _isSaving = true);
    final app = context.read<AppProvider>();

    await app.updateServerUrl(_serverUrlController.text.trim());
    await apiService.updateSettings(workers: _workers.round());

    if (mounted) {
      setState(() => _isSaving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Settings saved successfully!'),
          backgroundColor: AppColors.success,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppProvider>();
    final auth = context.watch<AuthProvider>();
    final status = app.status;
    final user = status?.user ?? auth.user;
    final isAuthorized = status?.isAuthorized == true || auth.isAuthorized;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 1. Account Section
          const Text('TELEGRAM ACCOUNT', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppColors.textMuted)),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.cardDark,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.borderDark),
            ),
            child: Row(
              children: [
                CircleAvatar(
                  radius: 22,
                  backgroundColor: isAuthorized ? AppColors.primary : AppColors.surfaceDark,
                  child: Icon(
                    isAuthorized ? Icons.person : Icons.person_outline,
                    color: Colors.white,
                    size: 24,
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        isAuthorized ? (user?.displayName ?? 'Connected User') : 'Not Connected',
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: AppColors.textPrimary),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        isAuthorized ? '@${user?.username ?? "no_username"}' : 'Link account to browse channels',
                        style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
                      ),
                    ],
                  ),
                ),
                if (isAuthorized)
                  OutlinedButton(
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.error,
                      side: const BorderSide(color: AppColors.error),
                    ),
                    onPressed: () => auth.logout(),
                    child: const Text('Logout'),
                  )
                else
                  FilledButton(
                    onPressed: () => QrLoginDialog.show(context),
                    child: const Text('Link'),
                  ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // 2. Performance & Parallel Workers
          const Text('PERFORMANCE & WORKERS', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppColors.textMuted)),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.cardDark,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.borderDark),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('Parallel MTProto Workers', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: AppColors.primary.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        '${_workers.round()}x Connections',
                        style: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.bold, fontSize: 13),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                const Text(
                  'Chunks are downloaded simultaneously across parallel connections for maximum speeds up to 100+ MB/s.',
                  style: TextStyle(fontSize: 11, color: AppColors.textMuted),
                ),
                Slider(
                  value: _workers,
                  min: 1,
                  max: 16,
                  divisions: 15,
                  activeColor: AppColors.primary,
                  onChanged: (val) => setState(() => _workers = val),
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // 3. Storage Metrics
          const Text('STORAGE & DISK', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppColors.textMuted)),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.cardDark,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.borderDark),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.folder_outlined, color: AppColors.primary, size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        status?.storage.downloadDir ?? 'Downloads/TelegramDownloader',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 13, color: AppColors.textPrimary),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      '${status?.storage.freeGb.toStringAsFixed(1) ?? "0"} GB Free',
                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppColors.success),
                    ),
                    Text(
                      'Total: ${status?.storage.totalGb.toStringAsFixed(1) ?? "0"} GB',
                      style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
                    ),
                  ],
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // 4. Server Connection
          const Text('BACKEND SERVER CONNECTION', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppColors.textMuted)),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.cardDark,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.borderDark),
            ),
            child: Column(
              children: [
                TextField(
                  controller: _serverUrlController,
                  decoration: InputDecoration(
                    labelText: 'Server API URL',
                    prefixIcon: const Icon(Icons.dns_outlined),
                    suffixIcon: Icon(
                      app.isServerConnected ? Icons.check_circle : Icons.error_outline,
                      color: app.isServerConnected ? AppColors.success : AppColors.error,
                      size: 20,
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: _isSaving ? null : _saveSettings,
                    child: _isSaving
                        ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                        : const Text('Save & Apply Settings'),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 32),
        ],
      ),
    );
  }
}
