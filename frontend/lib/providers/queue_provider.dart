import 'dart:async';
import 'package:flutter/material.dart';

import '../models/download_task.dart';
import '../services/api_service.dart';
import '../services/telemetry_ws.dart';

class QueueProvider extends ChangeNotifier {
  List<DownloadTask> _tasks = [];
  TelemetryData? _telemetry;
  bool _isLoading = false;
  StreamSubscription? _wsSub;
  Timer? _pollTimer;

  List<DownloadTask> get tasks => _tasks;
  TelemetryData? get telemetry => _telemetry;
  bool get isLoading => _isLoading;

  DownloadTask? get activeTask =>
      _telemetry?.activeTask ??
      _tasks.cast<DownloadTask?>().firstWhere(
            (t) => t?.isDownloading == true,
            orElse: () => null,
          );

  double get currentSpeedMbps => _telemetry?.overallSpeedMbps ?? 0.0;

  QueueProvider() {
    init();
  }

  void init() {
    refreshQueue();

    // Listen to real-time WebSocket telemetry
    _wsSub?.cancel();
    _wsSub = telemetryWs.stream.listen((data) {
      _telemetry = data;
      // If active task status changed or queue count changed, refresh queue
      notifyListeners();
    });

    // Periodic backup queue poll
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) {
      refreshQueue(silent: true);
    });
  }

  Future<void> refreshQueue({bool silent = false}) async {
    if (!silent) {
      _isLoading = true;
      notifyListeners();
    }

    final newTasks = await apiService.getQueue();
    _tasks = newTasks;

    if (!silent) {
      _isLoading = false;
    }
    notifyListeners();
  }

  Future<void> pauseTask(String taskId) async {
    await apiService.pauseTask(taskId);
    await refreshQueue(silent: true);
  }

  Future<void> resumeTask(String taskId) async {
    await apiService.resumeTask(taskId);
    await refreshQueue(silent: true);
  }

  Future<void> cancelTask(String taskId) async {
    await apiService.cancelTask(taskId);
    await refreshQueue(silent: true);
  }

  Future<void> clearCompleted() async {
    await apiService.clearCompleted();
    await refreshQueue(silent: true);
  }

  @override
  void dispose() {
    _wsSub?.cancel();
    _pollTimer?.cancel();
    super.dispose();
  }
}
