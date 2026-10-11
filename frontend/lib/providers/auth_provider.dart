import 'dart:async';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/system_status.dart';
import '../services/api_service.dart';

class AuthProvider extends ChangeNotifier {
  // Phone Auth State
  String? _phoneNumber;
  bool _codeSent = false;
  bool _needs2fa = false;
  bool _isLoading = false;

  // QR Auth State (optional secondary mode)
  String _qrStatus = 'idle';
  String? _qrUrl;
  String? _qrBase64;

  String? _errorMessage;
  UserProfile? _user;
  bool _isPolling = false;
  Timer? _pollTimer;

  String? get phoneNumber => _phoneNumber;
  bool get codeSent => _codeSent;
  bool get needs2fa => _needs2fa;
  bool get isLoading => _isLoading;

  String get qrStatus => _qrStatus;
  String? get qrUrl => _qrUrl;
  String? get qrBase64 => _qrBase64;
  String? get errorMessage => _errorMessage;
  UserProfile? get user => _user;
  bool get isAuthorized => _user != null || _qrStatus == 'authorized';

  void setUser(UserProfile? u) {
    _user = u;
    if (u != null) {
      _qrStatus = 'authorized';
    }
    notifyListeners();
  }

  void resetPhoneFlow() {
    _codeSent = false;
    _needs2fa = false;
    _errorMessage = null;
    _isLoading = false;
    notifyListeners();
  }

  // -------------------------------------------------------------------------
  // Phone Number & In-App Code Verification (Method 2)
  // -------------------------------------------------------------------------
  Future<bool> sendPhoneCode(String phone) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    final res = await apiService.sendPhoneCode(phone);
    _isLoading = false;

    if (res['success'] == true) {
      _phoneNumber = res['phone'] as String? ?? phone;
      _codeSent = true;
      notifyListeners();
      return true;
    } else {
      _errorMessage = res['error'] as String? ?? 'Failed to send verification code';
      notifyListeners();
      return false;
    }
  }

  Future<bool> verifyPhoneCode(String code) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    final res = await apiService.verifyPhoneCode(code);
    _isLoading = false;

    if (res['success'] == true) {
      _codeSent = false;
      _needs2fa = false;
      if (res['user'] != null) {
        _user = UserProfile.fromJson(res['user'] as Map<String, dynamic>);
      }
      notifyListeners();
      return true;
    } else if (res['needs_2fa'] == true) {
      _needs2fa = true;
      notifyListeners();
      return false;
    } else {
      _errorMessage = res['error'] as String? ?? 'Invalid verification code';
      notifyListeners();
      return false;
    }
  }

  // -------------------------------------------------------------------------
  // QR Code Device Linking Flow (Optional)
  // -------------------------------------------------------------------------
  Future<void> startQrAuth() async {
    _qrStatus = 'loading';
    _errorMessage = null;
    notifyListeners();

    final res = await apiService.getAuthQr();
    _qrStatus = res['status'] as String? ?? 'error';
    _qrUrl = res['url'] as String?;
    _qrBase64 = res['qr_base64'] as String?;
    _errorMessage = res['error'] as String?;

    if (res['user'] != null) {
      _user = UserProfile.fromJson(res['user'] as Map<String, dynamic>);
    }

    notifyListeners();
    _startPolling();
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _isPolling = true;

    _pollTimer = Timer.periodic(const Duration(milliseconds: 1500), (timer) async {
      if (!_isPolling) {
        timer.cancel();
        return;
      }

      final res = await apiService.pollAuth();
      final status = res['status'] as String? ?? 'pending';

      if (status == 'ready' && res['url'] != null) {
        _qrStatus = 'ready';
        _qrUrl = res['url'] as String?;
        _qrBase64 = res['qr_base64'] as String?;
        notifyListeners();
      } else if (status == 'needs_2fa') {
        _qrStatus = 'needs_2fa';
        _needs2fa = true;
        timer.cancel();
        _isPolling = false;
        notifyListeners();
      } else if (status == 'authorized') {
        _qrStatus = 'authorized';
        if (res['user'] != null) {
          _user = UserProfile.fromJson(res['user'] as Map<String, dynamic>);
        }
        timer.cancel();
        _isPolling = false;
        notifyListeners();
      } else if (status == 'error') {
        _qrStatus = 'error';
        _errorMessage = res['error'] as String?;
        timer.cancel();
        _isPolling = false;
        notifyListeners();
      }
    });
  }

  void stopPolling() {
    _isPolling = false;
    _pollTimer?.cancel();
  }

  Future<bool> openTelegramDeepLink() async {
    if (_qrUrl == null || _qrUrl!.isEmpty) return false;
    final uri = Uri.parse(_qrUrl!);
    try {
      return await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      return false;
    }
  }

  // -------------------------------------------------------------------------
  // 2FA Cloud Password Verification
  // -------------------------------------------------------------------------
  Future<bool> verify2fa(String password) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    final res = await apiService.submit2fa(password);
    _isLoading = false;

    if (res['success'] == true) {
      _qrStatus = 'authorized';
      _needs2fa = false;
      if (res['user'] != null) {
        _user = UserProfile.fromJson(res['user'] as Map<String, dynamic>);
      }
      notifyListeners();
      return true;
    } else {
      _errorMessage = res['error'] as String? ?? '2FA password verification failed';
      notifyListeners();
      return false;
    }
  }

  Future<void> logout() async {
    await apiService.logout();
    _user = null;
    _qrStatus = 'idle';
    _qrUrl = null;
    _qrBase64 = null;
    _errorMessage = null;
    _codeSent = false;
    _needs2fa = false;
    stopPolling();
    notifyListeners();
  }

  @override
  void dispose() {
    stopPolling();
    super.dispose();
  }
}
