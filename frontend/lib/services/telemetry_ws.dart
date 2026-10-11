import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/download_task.dart';

class TelemetryData {
  final DownloadTask? activeTask;
  final double overallSpeedMbps;
  final int queueCount;
  final int completedCount;
  final int activeCount;

  TelemetryData({
    this.activeTask,
    required this.overallSpeedMbps,
    required this.queueCount,
    required this.completedCount,
    required this.activeCount,
  });

  factory TelemetryData.fromJson(Map<String, dynamic> json) {
    return TelemetryData(
      activeTask: json['active_task'] != null
          ? DownloadTask.fromJson(json['active_task'] as Map<String, dynamic>)
          : null,
      overallSpeedMbps: (json['overall_speed_mbps'] as num?)?.toDouble() ?? 0.0,
      queueCount: json['queue_count'] as int? ?? 0,
      completedCount: json['completed_count'] as int? ?? 0,
      activeCount: json['active_count'] as int? ?? 0,
    );
  }
}

class TelemetryWsService {
  WebSocketChannel? _channel;
  StreamSubscription? _sub;
  final _controller = StreamController<TelemetryData>.broadcast();
  bool _isDisposed = false;
  Timer? _reconnectTimer;

  Stream<TelemetryData> get stream => _controller.stream;

  void connect(String httpBaseUrl) {
    _disconnect();
    if (_isDisposed) return;

    try {
      final wsUrl = httpBaseUrl
          .replaceFirst('http://', 'ws://')
          .replaceFirst('https://', 'wss://');
      final uri = Uri.parse('$wsUrl/ws/telemetry');

      _channel = WebSocketChannel.connect(uri);
      _sub = _channel!.stream.listen(
        (message) {
          try {
            final data = jsonDecode(message.toString()) as Map<String, dynamic>;
            _controller.add(TelemetryData.fromJson(data));
          } catch (_) {}
        },
        onError: (_) => _scheduleReconnect(httpBaseUrl),
        onDone: () => _scheduleReconnect(httpBaseUrl),
      );
    } catch (_) {
      _scheduleReconnect(httpBaseUrl);
    }
  }

  void _scheduleReconnect(String httpBaseUrl) {
    if (_isDisposed) return;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 3), () {
      connect(httpBaseUrl);
    });
  }

  void _disconnect() {
    _reconnectTimer?.cancel();
    _sub?.cancel();
    _sub = null;
    try {
      _channel?.sink.close();
    } catch (_) {}
    _channel = null;
  }

  void dispose() {
    _isDisposed = true;
    _disconnect();
    _controller.close();
  }
}

final telemetryWs = TelemetryWsService();
