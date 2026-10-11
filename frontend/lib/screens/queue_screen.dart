import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/theme.dart';
import '../providers/queue_provider.dart';
import '../widgets/media_card.dart';
import '../widgets/speed_hud.dart';

class QueueScreen extends StatelessWidget {
  const QueueScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final queue = context.watch<QueueProvider>();

    return RefreshIndicator(
      onRefresh: () => queue.refreshQueue(),
      color: AppColors.primary,
      backgroundColor: AppColors.surfaceDark,
      child: CustomScrollView(
        slivers: [
          // Real-time Speed HUD
          const SliverToBoxAdapter(
            child: SpeedHud(),
          ),

          // Action Bar: Tasks count & Clear Completed
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'DOWNLOAD QUEUE (${queue.tasks.length})',
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 0.5,
                      color: AppColors.textMuted,
                    ),
                  ),
                  if (queue.tasks.any((t) => t.isCompleted))
                    TextButton.icon(
                      icon: const Icon(Icons.cleaning_services_outlined, size: 14),
                      label: const Text('Clear Finished'),
                      style: TextButton.styleFrom(
                        foregroundColor: AppColors.textMuted,
                        textStyle: const TextStyle(fontSize: 12),
                      ),
                      onPressed: () => queue.clearCompleted(),
                    ),
                ],
              ),
            ),
          ),

          // Task List or Empty State
          if (queue.tasks.isEmpty)
            SliverFillRemaining(
              hasScrollBody: false,
              child: Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: AppColors.surfaceDark,
                        shape: BoxShape.circle,
                        border: Border.all(color: AppColors.borderDark),
                      ),
                      child: const Icon(Icons.inbox_outlined, size: 36, color: AppColors.textMuted),
                    ),
                    const SizedBox(height: 14),
                    const Text(
                      'No Active Downloads',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'Forward files to your bot or browse channels in Explorer',
                      style: TextStyle(fontSize: 12, color: AppColors.textMuted),
                    ),
                  ],
                ),
              ),
            )
          else
            SliverList(
              delegate: SliverChildBuilderDelegate(
                (context, index) {
                  final task = queue.tasks[index];
                  return MediaCard(task: task);
                },
                childCount: queue.tasks.length,
              ),
            ),

          const SliverToBoxAdapter(child: SizedBox(height: 24)),
        ],
      ),
    );
  }
}
