import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../core/constants.dart';
import '../models/chat_dialog.dart';
import '../models/download_task.dart';
import '../models/media_item.dart';
import '../models/system_status.dart';

class ApiService {
  String _baseUrl = AppConstants.defaultServerUrl;

  String get baseUrl => _baseUrl;

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _baseUrl = prefs.getString(AppConstants.serverUrlKey) ?? AppConstants.defaultServerUrl;
  }

  Future<void> updateBaseUrl(String newUrl) async {
    _baseUrl = newUrl.trim().replaceAll(RegExp(r'/+$'), '');
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConstants.serverUrlKey, _baseUrl);
  }

  Uri _uri(String path, [Map<String, dynamic>? queryParams]) {
    final cleanPath = path.startsWith('/') ? path : '/$path';
    final fullUrl = '$_baseUrl$cleanPath';
    return Uri.parse(fullUrl).replace(queryParameters: queryParams);
  }

  // 1. System & Status
  Future<SystemStatus?> getStatus() async {
    try {
      final res = await http.get(_uri('/api/status')).timeout(const Duration(seconds: 4));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        return SystemStatus.fromJson(data);
      }
    } catch (_) {}
    return null;
  }

  // 2. Authentication
  Future<Map<String, dynamic>> getAuthQr() async {
    try {
      final res = await http.get(_uri('/api/auth/qr')).timeout(const Duration(seconds: 8));
      if (res.statusCode == 200) {
        return jsonDecode(res.body) as Map<String, dynamic>;
      }
    } catch (e) {
      return {'status': 'error', 'error': e.toString()};
    }
    return {'status': 'error', 'error': 'Failed to reach server'};
  }

  Future<Map<String, dynamic>> pollAuth() async {
    try {
      final res = await http.get(_uri('/api/auth/poll')).timeout(const Duration(seconds: 4));
      if (res.statusCode == 200) {
        return jsonDecode(res.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return {'status': 'pending'};
  }

  Future<Map<String, dynamic>> sendPhoneCode(String phone) async {
    try {
      final res = await http.post(
        _uri('/api/auth/phone/send-code'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'phone': phone}),
      ).timeout(const Duration(seconds: 12));
      return jsonDecode(res.body) as Map<String, dynamic>;
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  Future<Map<String, dynamic>> verifyPhoneCode(String code) async {
    try {
      final res = await http.post(
        _uri('/api/auth/phone/verify-code'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'code': code}),
      ).timeout(const Duration(seconds: 12));
      return jsonDecode(res.body) as Map<String, dynamic>;
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  Future<Map<String, dynamic>> submit2fa(String password) async {
    try {
      final res = await http.post(
        _uri('/api/auth/2fa'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'password': password}),
      ).timeout(const Duration(seconds: 10));
      return jsonDecode(res.body) as Map<String, dynamic>;
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  Future<bool> logout() async {
    try {
      final res = await http.post(_uri('/api/auth/logout')).timeout(const Duration(seconds: 5));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // 3. Dialogs & Media
  Future<List<ChatDialog>> getDialogs() async {
    try {
      final res = await http.get(_uri('/api/dialogs')).timeout(const Duration(seconds: 8));
      if (res.statusCode == 200) {
        final list = jsonDecode(res.body) as List<dynamic>;
        return list.map((e) => ChatDialog.fromJson(e as Map<String, dynamic>)).toList();
      }
    } catch (_) {}
    return [];
  }

  Future<List<MediaItem>> getDialogMedia(int chatId, {int limit = 50, int offsetId = 0}) async {
    try {
      final res = await http.get(
        _uri('/api/dialogs/$chatId/media', {
          'limit': limit.toString(),
          'offset_id': offsetId.toString(),
        }),
      ).timeout(const Duration(seconds: 10));

      if (res.statusCode == 200) {
        final list = jsonDecode(res.body) as List<dynamic>;
        return list.map((e) => MediaItem.fromJson(e as Map<String, dynamic>)).toList();
      }
    } catch (_) {}
    return [];
  }

  // 4. Download Queue
  Future<List<DownloadTask>> getQueue() async {
    try {
      final res = await http.get(_uri('/api/queue')).timeout(const Duration(seconds: 4));
      if (res.statusCode == 200) {
        final list = jsonDecode(res.body) as List<dynamic>;
        return list.map((e) => DownloadTask.fromJson(e as Map<String, dynamic>)).toList();
      }
    } catch (_) {}
    return [];
  }

  Future<bool> addToQueue({
    required int chatId,
    required int messageId,
    required String title,
    required int totalBytes,
    String? channelTitle,
  }) async {
    try {
      final res = await http.post(
        _uri('/api/queue/add'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'chat_id': chatId,
          'message_id': messageId,
          'title': title,
          'total_bytes': totalBytes,
          'channel_title': channelTitle,
        }),
      ).timeout(const Duration(seconds: 5));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<bool> pauseTask(String taskId) async {
    try {
      final res = await http.post(_uri('/api/queue/$taskId/pause'));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<bool> resumeTask(String taskId) async {
    try {
      final res = await http.post(_uri('/api/queue/$taskId/resume'));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<bool> cancelTask(String taskId) async {
    try {
      final res = await http.post(_uri('/api/queue/$taskId/cancel'));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<bool> clearCompleted() async {
    try {
      final res = await http.post(_uri('/api/queue/clear'));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // 5. Bot Forwarded Files
  Future<List<DownloadTask>> getBotFiles() async {
    try {
      final res = await http.get(_uri('/api/bot/files')).timeout(const Duration(seconds: 4));
      if (res.statusCode == 200) {
        final list = jsonDecode(res.body) as List<dynamic>;
        return list.map((e) => DownloadTask.fromJson(e as Map<String, dynamic>)).toList();
      }
    } catch (_) {}
    return [];
  }

  // 6. Settings
  Future<Map<String, dynamic>?> getSettings() async {
    try {
      final res = await http.get(_uri('/api/settings')).timeout(const Duration(seconds: 4));
      if (res.statusCode == 200) {
        return jsonDecode(res.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return null;
  }

  Future<bool> updateSettings({int? workers, String? downloadDir, String? botToken}) async {
    try {
      final body = <String, dynamic>{};
      if (workers != null) body['parallel_workers'] = workers;
      if (downloadDir != null) body['download_dir'] = downloadDir;
      if (botToken != null) body['bot_token'] = botToken;

      final res = await http.post(
        _uri('/api/settings'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 5));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}

final apiService = ApiService();
