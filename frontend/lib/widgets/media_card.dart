import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/theme.dart';
import '../models/download_task.dart';
import '../providers/queue_provider.dart';
import 'status_badge.dart';

class MediaCard extends StatelessWidget {
  final DownloadTask task;

  const MediaCard({super.key, required this.task});

  IconData _getFileIcon(String title) {
    final lower = title.toLowerCase();
    if (lower.endsWith('.mp4') || lower.endsWith('.mkv') || lower.endsWith('.avi') || lower.endsWith('.mov')) {
      return Icons.movie_outlined;
    }
    if (lower.endsWith('.mp3') || lower.endsWith('.flac') || lower.endsWith('.m4a') || lower.endsWith('.wav')) {
      return Icons.music_note_outlined;
    }
    if (lower.endsWith('.zip') || lower.endsWith('.rar') || lower.endsWith('.7z') || lower.endsWith('.tar')) {
      return Icons.folder_zip_outlined;
    }
    if (lower.endsWith('.pdf') || lower.endsWith('.doc') || lower.endsWith('.docx') || lower.endsWith('.txt')) {
      return Icons.description_outlined;
    }
    if (lower.endsWith('.jpg') || lower.endsWith('.jpeg') || lower.endsWith('.png') || lower.endsWith('.webp')) {
      return Icons.image_outlined;
    }
    return Icons.insert_drive_file_outlined;
  }

  @override
  Widget build(BuildContext context) {
    final queue = context.read<QueueProvider>();

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      padding: const EdgeInsets.all(14),
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
              // File Type Icon
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: AppColors.surfaceDark,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(_getFileIcon(task.title), color: AppColors.primary, size: 22),
              ),
              const SizedBox(width: 12),

              // Title and Channel
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      task.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 14,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Row(
                      children: [
                        Text(
                          task.formattedSize,
                          style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
                        ),
                        if (task.channelTitle != null) ...[
                          const SizedBox(width: 6),
                          const Text('•', style: TextStyle(fontSize: 12, color: AppColors.textMuted)),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              task.channelTitle!,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 12, color: AppColors.textMuted),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ],
                ),
              ),

              const SizedBox(width: 8),
              StatusBadge(status: task.status),
            ],
          ),

          // Progress bar for active / paused downloads
          if (task.isDownloading || task.isPaused) ...[
            const SizedBox(height: 10),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: task.progressFraction,
                minHeight: 5,
                backgroundColor: AppColors.bgDark,
                valueColor: AlwaysStoppedAnimation<Color>(
                  task.isPaused ? AppColors.warning : AppColors.primary,
                ),
              ),
            ),
            const SizedBox(height: 6),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  '${task.formattedDownloaded} / ${task.formattedSize}',
                  style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
                ),
                Text(
                  '${task.progressPercentage}%',
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimary,
                  ),
                ),
              ],
            ),
          ],

          // Action Buttons
          if (task.isDownloading || task.isPaused || task.isQueued) ...[
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                if (task.isDownloading)
                  TextButton.icon(
                    icon: const Icon(Icons.pause, size: 16),
                    label: const Text('Pause'),
                    style: TextButton.styleFrom(foregroundColor: AppColors.warning),
                    onPressed: () => queue.pauseTask(task.id),
                  ),
                if (task.isPaused)
                  TextButton.icon(
                    icon: const Icon(Icons.play_arrow, size: 16),
                    label: const Text('Resume'),
                    style: TextButton.styleFrom(foregroundColor: AppColors.primary),
                    onPressed: () => queue.resumeTask(task.id),
                  ),
                TextButton.icon(
                  icon: const Icon(Icons.close, size: 16),
                  label: const Text('Cancel'),
                  style: TextButton.styleFrom(foregroundColor: AppColors.error),
                  onPressed: () => queue.cancelTask(task.id),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
