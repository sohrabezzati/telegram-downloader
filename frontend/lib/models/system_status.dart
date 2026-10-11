class UserProfile {
  final int id;
  final String firstName;
  final String? lastName;
  final String? username;
  final String displayName;
  final bool isPremium;

  UserProfile({
    required this.id,
    required this.firstName,
    this.lastName,
    this.username,
    required this.displayName,
    this.isPremium = false,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      id: json['id'] as int? ?? 0,
      firstName: json['first_name'] as String? ?? '',
      lastName: json['last_name'] as String?,
      username: json['username'] as String?,
      displayName: json['display_name'] as String? ?? 'Telegram User',
      isPremium: json['is_premium'] as bool? ?? false,
    );
  }
}

class StorageInfo {
  final String downloadDir;
  final int freeBytes;
  final int totalBytes;
  final double freeGb;
  final double totalGb;
  final double freePercentage;
  final bool lowSpace;

  StorageInfo({
    required this.downloadDir,
    required this.freeBytes,
    required this.totalBytes,
    required this.freeGb,
    required this.totalGb,
    required this.freePercentage,
    required this.lowSpace,
  });

  factory StorageInfo.fromJson(Map<String, dynamic> json) {
    return StorageInfo(
      downloadDir: json['download_dir'] as String? ?? '',
      freeBytes: json['free_bytes'] as int? ?? 0,
      totalBytes: json['total_bytes'] as int? ?? 0,
      freeGb: (json['free_gb'] as num?)?.toDouble() ?? 0.0,
      totalGb: (json['total_gb'] as num?)?.toDouble() ?? 0.0,
      freePercentage: (json['free_percentage'] as num?)?.toDouble() ?? 0.0,
      lowSpace: json['low_space'] as bool? ?? false,
    );
  }
}

class SystemStatus {
  final bool online;
  final bool isAuthorized;
  final UserProfile? user;
  final bool botRunning;
  final String? botUsername;
  final StorageInfo storage;
  final int workers;
  final int totalQueued;
  final int completedCount;

  SystemStatus({
    required this.online,
    required this.isAuthorized,
    this.user,
    required this.botRunning,
    this.botUsername,
    required this.storage,
    required this.workers,
    required this.totalQueued,
    required this.completedCount,
  });

  factory SystemStatus.fromJson(Map<String, dynamic> json) {
    final auth = json['auth'] as Map<String, dynamic>? ?? {};
    final bot = json['bot'] as Map<String, dynamic>? ?? {};
    final storageJson = json['storage'] as Map<String, dynamic>? ?? {};
    final engine = json['engine'] as Map<String, dynamic>? ?? {};

    return SystemStatus(
      online: json['online'] as bool? ?? false,
      isAuthorized: auth['is_authorized'] as bool? ?? false,
      user: auth['user'] != null ? UserProfile.fromJson(auth['user']) : null,
      botRunning: bot['is_running'] as bool? ?? false,
      botUsername: bot['username'] as String?,
      storage: StorageInfo.fromJson(storageJson),
      workers: engine['parallel_workers'] as int? ?? 16,
      totalQueued: engine['total_queued'] as int? ?? 0,
      completedCount: engine['completed_count'] as int? ?? 0,
    );
  }
}
