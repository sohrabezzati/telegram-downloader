class MediaItem {
  final int chatId;
  final int messageId;
  final String title;
  final int totalBytes;
  final String date;
  final String mimeType;
  final String? queueStatus;

  MediaItem({
    required this.chatId,
    required this.messageId,
    required this.title,
    required this.totalBytes,
    required this.date,
    required this.mimeType,
    this.queueStatus,
  });

  factory MediaItem.fromJson(Map<String, dynamic> json) {
    return MediaItem(
      chatId: json['chat_id'] as int? ?? 0,
      messageId: json['message_id'] as int? ?? 0,
      title: json['title'] as String? ?? 'media_file',
      totalBytes: json['total_bytes'] as int? ?? 0,
      date: json['date'] as String? ?? '',
      mimeType: json['mime_type'] as String? ?? 'application/octet-stream',
      queueStatus: json['queue_status'] as String?,
    );
  }

  bool get isQueuedOrDownloading =>
      queueStatus == 'QUEUED' || queueStatus == 'DOWNLOADING';
  bool get isCompleted => queueStatus == 'COMPLETED';

  String get formattedSize {
    if (totalBytes <= 0) return 'Unknown size';
    if (totalBytes < 1024 * 1024) {
      return '${(totalBytes / 1024).toStringAsFixed(1)} KB';
    } else if (totalBytes < 1024 * 1024 * 1024) {
      return '${(totalBytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    } else {
      return '${(totalBytes / (1024 * 1024 * 1024)).toStringAsFixed(2)} GB';
    }
  }

  bool get isVideo =>
      mimeType.startsWith('video') ||
      title.endsWith('.mp4') ||
      title.endsWith('.mkv');
  bool get isAudio =>
      mimeType.startsWith('audio') ||
      title.endsWith('.mp3') ||
      title.endsWith('.flac');
  bool get isImage =>
      mimeType.startsWith('image') ||
      title.endsWith('.jpg') ||
      title.endsWith('.png');
}
