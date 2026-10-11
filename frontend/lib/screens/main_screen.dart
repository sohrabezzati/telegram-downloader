import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/theme.dart';
import '../providers/app_provider.dart';
import '../providers/auth_provider.dart';
import '../widgets/qr_dialog.dart';
import 'bot_screen.dart';
import 'explorer_screen.dart';
import 'queue_screen.dart';
import 'settings_screen.dart';

class MainScreen extends StatelessWidget {
  const MainScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppProvider>();
    final auth = context.watch<AuthProvider>();
    final status = app.status;
    final isAuthorized = status?.isAuthorized == true || auth.isAuthorized;
    final user = status?.user ?? auth.user;

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: AppColors.primary,
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.bolt, color: Colors.white, size: 20),
            ),
            const SizedBox(width: 10),
            const Text(
              'Telegram Downloader',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
            ),
          ],
        ),
        actions: [
          // Account Badge or Link Button
          if (isAuthorized)
            Padding(
              padding: const EdgeInsets.only(right: 12),
              child: ActionChip(
                avatar: const Icon(Icons.account_circle, size: 18, color: AppColors.primary),
                label: Text(
                  user?.displayName ?? 'Connected',
                  style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                ),
                backgroundColor: AppColors.cardDark,
                side: const BorderSide(color: AppColors.borderDark),
                onPressed: () => app.setTabIndex(3), // Open Settings
              ),
            )
          else
            Padding(
              padding: const EdgeInsets.only(right: 12),
              child: FilledButton.tonalIcon(
                icon: const Icon(Icons.qr_code_2, size: 16),
                label: const Text('Connect', style: TextStyle(fontSize: 12)),
                style: FilledButton.styleFrom(
                  backgroundColor: AppColors.primary.withValues(alpha: 0.2),
                  foregroundColor: AppColors.primaryLight,
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                ),
                onPressed: () => QrLoginDialog.show(context),
              ),
            ),
        ],
      ),
      body: IndexedStack(
        index: app.currentTabIndex,
        children: const [
          QueueScreen(),
          BotScreen(),
          ExplorerScreen(),
          SettingsScreen(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: app.currentTabIndex,
        onDestinationSelected: app.setTabIndex,
        backgroundColor: AppColors.surfaceDark,
        indicatorColor: AppColors.primary.withValues(alpha: 0.25),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.speed),
            selectedIcon: Icon(Icons.speed, color: AppColors.primaryLight),
            label: 'Downloads',
          ),
          NavigationDestination(
            icon: Icon(Icons.smart_toy_outlined),
            selectedIcon: Icon(Icons.smart_toy, color: AppColors.primaryLight),
            label: 'Bot Inbox',
          ),
          NavigationDestination(
            icon: Icon(Icons.folder_outlined),
            selectedIcon: Icon(Icons.folder, color: AppColors.primaryLight),
            label: 'Explorer',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            selectedIcon: Icon(Icons.settings, color: AppColors.primaryLight),
            label: 'Settings',
          ),
        ],
      ),
    );
  }
}
