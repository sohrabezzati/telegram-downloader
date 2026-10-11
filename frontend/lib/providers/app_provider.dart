import 'dart:async';
import 'package:flutter/material.dart';

import '../models/system_status.dart';
import '../services/api_service.dart';
import '../services/telemetry_ws.dart';

class AppProvider extends ChangeNotifier {
  SystemStatus? _status;
  int _currentTabIndex = 0;
  bool _isLoading = false;
  Timer? _statusTimer;

  SystemStatus? get status => _status;
  int get currentTabIndex => _currentTabIndex;
  bool get isLoading => _isLoading;
  bool get isServerConnected => _status != null && _status!.online;

  AppProvider() {
    init();
  }

  Future<void> init() async {
    await apiService.init();
    telemetryWs.connect(apiService.baseUrl);
    await refreshStatus();

    _statusTimer?.cancel();
    _statusTimer = Timer.periodic(const Duration(seconds: 4), (_) {
      refreshStatus();
    });
  }

  void setTabIndex(int index) {
    _currentTabIndex = index;
    notifyListeners();
  }

  Future<void> refreshStatus() async {
    final s = await apiService.getStatus();
    if (s != _status) {
      _status = s;
      notifyListeners();
    }
  }

  Future<void> updateServerUrl(String newUrl) async {
    _isLoading = true;
    notifyListeners();

    await apiService.updateBaseUrl(newUrl);
    telemetryWs.connect(apiService.baseUrl);
    await refreshStatus();

    _isLoading = false;
    notifyListeners();
  }

  @override
  void dispose() {
    _statusTimer?.cancel();
    super.dispose();
  }
}
