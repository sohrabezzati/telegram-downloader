import 'package:flutter/material.dart';
import '../core/theme.dart';

class StatusBadge extends StatelessWidget {
  final String status;

  const StatusBadge({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    Color bg;
    Color fg;
    String label;
    IconData icon;

    switch (status.toUpperCase()) {
      case 'DOWNLOADING':
        bg = AppColors.primary.withValues(alpha: 0.15);
        fg = AppColors.primary;
        label = 'Downloading';
        icon = Icons.downloading;
        break;
      case 'COMPLETED':
        bg = AppColors.success.withValues(alpha: 0.15);
        fg = AppColors.success;
        label = 'Downloaded';
        icon = Icons.check_circle_outline;
        break;
      case 'PAUSED':
        bg = AppColors.warning.withValues(alpha: 0.15);
        fg = AppColors.warning;
        label = 'Paused';
        icon = Icons.pause_circle_outline;
        break;
      case 'FAILED':
        bg = AppColors.error.withValues(alpha: 0.15);
        fg = AppColors.error;
        label = 'Failed';
        icon = Icons.error_outline;
        break;
      case 'QUEUED':
      default:
        bg = AppColors.textMuted.withValues(alpha: 0.15);
        fg = AppColors.textMuted;
        label = 'Queued';
        icon = Icons.schedule;
        break;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: fg.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: fg),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              color: fg,
              fontSize: 11,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}
