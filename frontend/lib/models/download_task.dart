class DownloadTask {
  final String id;
  final String title;
  final int totalBytes;
  final int downloadedBytes;
  final double progressFraction;
  final int progressPercentage;
  final double speedMbps;
  final double etaSeconds;
  final String status;
  final String? errorMessage;
  final String source;
  final String? channelTitle;
  final int? chatId;
  final int? messageId;
  final Map<String, dynamic> workerProgress;

  DownloadTask({
    required this.id,
    required this.title,
    required this.totalBytes,
    required this.downloadedBytes,
    required this.progressFraction,
    required this.progressPercentage,
    required this.speedMbps,
    required this.etaSeconds,
    required this.status,
    this.errorMessage,
    required this.source,
    this.channelTitle,
    this.chatId,
    this.messageId,
    this.workerProgress = const {},
  });

  factory DownloadTask.fromJson(Map<String, dynamic> json) {
    return DownloadTask(
      id: json['id'] as String? ?? '',
      title: json['title'] as String? ?? 'Unnamed File',
      totalBytes: json['total_bytes'] as int? ?? 0,
      downloadedBytes: json['downloaded_bytes'] as int? ?? 0,
      progressFraction: (json['progress_fraction'] as num?)?.toDouble() ?? 0.0,
      progressPercentage: json['progress_percentage'] as int? ?? 0,
      speedMbps: (json['speed_mbps'] as num?)?.toDouble() ?? 0.0,
      etaSeconds: (json['eta_seconds'] as num?)?.toDouble() ?? 0.0,
      status: json['status'] as String? ?? 'QUEUED',
      errorMessage: json['error_message'] as String?,
      source: json['source'] as String? ?? 'DIRECT',
      channelTitle: json['channel_title'] as String?,
      chatId: json['chat_id'] as int?,
      messageId: json['message_id'] as int?,
      workerProgress: json['worker_progress'] as Map<String, dynamic>? ?? {},
    );
  }

  bool get isDownloading => status == 'DOWNLOADING';
  bool get isCompleted => status == 'COMPLETED';
  bool get isPaused => status == 'PAUSED';
  bool get isFailed => status == 'FAILED';
  bool get isQueued => status == 'QUEUED';

  String get formattedSize {
    if (totalBytes <= 0) return '0 B';
    if (totalBytes < 1024 * 1024) {
      return '${(totalBytes / 1024).toStringAsFixed(1)} KB';
    } else if (totalBytes < 1024 * 1024 * 1024) {
      return '${(totalBytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    } else {
      return '${(totalBytes / (1024 * 1024 * 1024)).toStringAsFixed(2)} GB';
    }
  }

  String get formattedDownloaded {
    if (downloadedBytes < 1024 * 1024) {
      return '${(downloadedBytes / 1024).toStringAsFixed(1)} KB';
    } else if (downloadedBytes < 1024 * 1024 * 1024) {
      return '${(downloadedBytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    } else {
      return '${(downloadedBytes / (1024 * 1024 * 1024)).toStringAsFixed(2)} GB';
    }
  }

  String get formattedEta {
    if (etaSeconds <= 0 || !isDownloading) return '';
    if (etaSeconds < 60) return '${etaSeconds.toInt()}s';
    final mins = (etaSeconds / 60).floor();
    final secs = (etaSeconds % 60).toInt();
    return '${mins}m ${secs}s';
  }
}
