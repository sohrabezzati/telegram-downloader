import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/theme.dart';
import '../providers/auth_provider.dart';

class QrLoginDialog extends StatefulWidget {
  const QrLoginDialog({super.key});

  static Future<void> show(BuildContext context) {
    return showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const QrLoginDialog(),
    );
  }

  @override
  State<QrLoginDialog> createState() => _QrLoginDialogState();
}

class _QrLoginDialogState extends State<QrLoginDialog> {
  final _phoneController = TextEditingController();
  final _codeController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _showQrMode = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AuthProvider>().resetPhoneFlow();
    });
  }

  @override
  void dispose() {
    _phoneController.dispose();
    _codeController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Uint8List? _decodeBase64Image(String? raw) {
    if (raw == null || raw.isEmpty) return null;
    try {
      final clean = raw.contains(',') ? raw.split(',')[1] : raw;
      return base64Decode(clean);
    } catch (_) {
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();

    // If authorized, auto close dialog
    if (auth.isAuthorized) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (Navigator.of(context).canPop()) {
          Navigator.of(context).pop();
        }
      });
    }

    return AlertDialog(
      backgroundColor: AppColors.surfaceDark,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      title: Row(
        children: [
          Icon(
            _showQrMode ? Icons.qr_code_2 : Icons.phone_iphone,
            color: AppColors.primary,
            size: 26,
          ),
          const SizedBox(width: 10),
          Text(
            _showQrMode ? 'Link via QR Code' : 'Log in via Phone Number',
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
        ],
      ),
      content: SingleChildScrollView(
        child: SizedBox(
          width: 360,
          child: _showQrMode ? _buildQrSection(auth) : _buildPhoneSection(auth),
        ),
      ),
      actions: [
        if (!_showQrMode && (auth.codeSent || auth.needs2fa))
          TextButton(
            onPressed: () => auth.resetPhoneFlow(),
            child: const Text('Change Phone', style: TextStyle(color: AppColors.primaryLight)),
          ),
        TextButton(
          onPressed: () {
            auth.stopPolling();
            auth.resetPhoneFlow();
            Navigator.of(context).pop();
          },
          child: const Text('Cancel', style: TextStyle(color: AppColors.textMuted)),
        ),
      ],
    );
  }

  // -------------------------------------------------------------------------
  // Primary Method: Phone Number & In-App Code Verification
  // -------------------------------------------------------------------------
  Widget _buildPhoneSection(AuthProvider auth) {
    if (auth.needs2fa) {
      return _build2faStep(auth);
    } else if (auth.codeSent) {
      return _buildCodeStep(auth);
    } else {
      return _buildPhoneStep(auth);
    }
  }

  // Step 1: Phone input
  Widget _buildPhoneStep(AuthProvider auth) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppColors.cardDark,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: AppColors.borderDark),
          ),
          child: const Row(
            children: [
              Icon(Icons.info_outline, size: 20, color: AppColors.primary),
              SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Enter your phone number in international format (+1...). Telegram will send a 5-digit verification code directly to your Telegram app.',
                  style: TextStyle(fontSize: 11, color: AppColors.textSecondary),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: _phoneController,
          keyboardType: TextInputType.phone,
          style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
          decoration: const InputDecoration(
            labelText: 'Phone Number',
            hintText: '+1 234 567 8900',
            prefixIcon: Icon(Icons.phone, color: AppColors.primary),
          ),
        ),
        if (auth.errorMessage != null) ...[
          const SizedBox(height: 10),
          Text(
            auth.errorMessage!,
            style: const TextStyle(color: AppColors.error, fontSize: 12),
          ),
        ],
        const SizedBox(height: 18),
        SizedBox(
          width: double.infinity,
          height: 46,
          child: FilledButton.icon(
            icon: auth.isLoading
                ? const SizedBox.shrink()
                : const Icon(Icons.arrow_forward, size: 18),
            label: auth.isLoading
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Text('Send Verification Code'),
            onPressed: auth.isLoading
                ? null
                : () {
                    final phone = _phoneController.text.trim();
                    if (phone.isNotEmpty) {
                      auth.sendPhoneCode(phone);
                    }
                  },
          ),
        ),
        const SizedBox(height: 16),
        Center(
          child: TextButton.icon(
            icon: const Icon(Icons.qr_code, size: 16),
            label: const Text('Or log in using QR Code scanner', style: TextStyle(fontSize: 12)),
            style: TextButton.styleFrom(foregroundColor: AppColors.textMuted),
            onPressed: () {
              setState(() => _showQrMode = true);
              auth.startQrAuth();
            },
          ),
        ),
      ],
    );
  }

  // Step 2: 5-digit code verification
  Widget _buildCodeStep(AuthProvider auth) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppColors.success.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: AppColors.success.withValues(alpha: 0.3)),
          ),
          child: Row(
            children: [
              const Icon(Icons.mark_chat_unread_outlined, size: 22, color: AppColors.success),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Code sent to your active Telegram app sessions for ${auth.phoneNumber ?? ""}. Check your in-app service messages!',
                  style: const TextStyle(fontSize: 11, color: AppColors.textPrimary),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        TextField(
          controller: _codeController,
          keyboardType: TextInputType.number,
          autofocus: true,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, letterSpacing: 8),
          decoration: const InputDecoration(
            labelText: '5-Digit Code',
            hintText: '12345',
            prefixIcon: Icon(Icons.lock_open, color: AppColors.primary),
          ),
        ),
        if (auth.errorMessage != null) ...[
          const SizedBox(height: 10),
          Text(
            auth.errorMessage!,
            style: const TextStyle(color: AppColors.error, fontSize: 12),
          ),
        ],
        const SizedBox(height: 18),
        SizedBox(
          width: double.infinity,
          height: 46,
          child: FilledButton.icon(
            icon: auth.isLoading
                ? const SizedBox.shrink()
                : const Icon(Icons.check_circle_outline, size: 18),
            label: auth.isLoading
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Text('Verify Code & Sign In'),
            onPressed: auth.isLoading
                ? null
                : () {
                    final code = _codeController.text.trim();
                    if (code.isNotEmpty) {
                      auth.verifyPhoneCode(code);
                    }
                  },
          ),
        ),
      ],
    );
  }

  // Step 3: 2FA Cloud Password
  Widget _build2faStep(AuthProvider auth) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppColors.warning.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: AppColors.warning.withValues(alpha: 0.3)),
          ),
          child: const Row(
            children: [
              Icon(Icons.shield_outlined, size: 22, color: AppColors.warning),
              SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Two-Step Verification is active on your account. Please enter your Cloud Password to complete login:',
                  style: TextStyle(fontSize: 11, color: AppColors.textPrimary),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        TextField(
          controller: _passwordController,
          obscureText: true,
          autofocus: true,
          decoration: const InputDecoration(
            labelText: '2FA Cloud Password',
            prefixIcon: Icon(Icons.password, color: AppColors.warning),
          ),
        ),
        if (auth.errorMessage != null) ...[
          const SizedBox(height: 10),
          Text(
            auth.errorMessage!,
            style: const TextStyle(color: AppColors.error, fontSize: 12),
          ),
        ],
        const SizedBox(height: 18),
        SizedBox(
          width: double.infinity,
          height: 46,
          child: FilledButton.icon(
            icon: auth.isLoading
                ? const SizedBox.shrink()
                : const Icon(Icons.verified_user, size: 18),
            label: auth.isLoading
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Text('Verify Password & Finish'),
            onPressed: auth.isLoading
                ? null
                : () {
                    final pwd = _passwordController.text.trim();
                    if (pwd.isNotEmpty) {
                      auth.verify2fa(pwd);
                    }
                  },
          ),
        ),
      ],
    );
  }

  // -------------------------------------------------------------------------
  // Optional Secondary Method: QR Code Device Linking
  // -------------------------------------------------------------------------
  Widget _buildQrSection(AuthProvider auth) {
    final qrBytes = _decodeBase64Image(auth.qrBase64);

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Text(
          'Open Telegram ➔ Settings ➔ Devices ➔ Link Desktop Device and scan below:',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 12, color: AppColors.textMuted),
        ),
        const SizedBox(height: 14),
        Container(
          width: 210,
          height: 210,
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
          ),
          alignment: Alignment.center,
          child: qrBytes != null && auth.qrStatus != 'loading'
              ? ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: Image.memory(
                    qrBytes,
                    width: 200,
                    height: 200,
                    fit: BoxFit.contain,
                  ),
                )
              : const Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    SizedBox(
                      width: 28,
                      height: 28,
                      child: CircularProgressIndicator(strokeWidth: 3, color: AppColors.primary),
                    ),
                    SizedBox(height: 10),
                    Text('Generating QR token...', style: TextStyle(color: Colors.black54, fontSize: 11)),
                  ],
                ),
        ),
        const SizedBox(height: 16),
        TextButton.icon(
          icon: const Icon(Icons.phone_iphone, size: 16),
          label: const Text('Back to Phone Number Login', style: TextStyle(fontSize: 12)),
          style: TextButton.styleFrom(foregroundColor: AppColors.primaryLight),
          onPressed: () {
            setState(() => _showQrMode = false);
            auth.stopPolling();
            auth.resetPhoneFlow();
          },
        ),
      ],
    );
  }
}
