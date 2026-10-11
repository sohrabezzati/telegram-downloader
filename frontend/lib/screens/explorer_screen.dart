import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/theme.dart';
import '../models/chat_dialog.dart';
import '../models/media_item.dart';
import '../providers/app_provider.dart';
import '../providers/queue_provider.dart';
import '../services/api_service.dart';
import '../widgets/qr_dialog.dart';

class ExplorerScreen extends StatefulWidget {
  const ExplorerScreen({super.key});

  @override
  State<ExplorerScreen> createState() => _ExplorerScreenState();
}

class _ExplorerScreenState extends State<ExplorerScreen> {
  List<ChatDialog> _dialogs = [];
  ChatDialog? _selectedDialog;
  List<MediaItem> _mediaItems = [];
  bool _isLoadingDialogs = false;
  bool _isLoadingMedia = false;
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    _loadDialogs();
  }

  Future<void> _loadDialogs() async {
    final app = context.read<AppProvider>();
    if (app.status?.isAuthorized != true) return;

    setState(() => _isLoadingDialogs = true);
    final dialogs = await apiService.getDialogs();
    if (mounted) {
      setState(() {
        _dialogs = dialogs;
        _isLoadingDialogs = false;
        if (_dialogs.isNotEmpty && _selectedDialog == null) {
          _selectDialog(_dialogs.first);
        }
      });
    }
  }

  Future<void> _selectDialog(ChatDialog dialog) async {
    setState(() {
      _selectedDialog = dialog;
      _isLoadingMedia = true;
      _mediaItems = [];
    });

    final items = await apiService.getDialogMedia(dialog.id);
    if (mounted) {
      setState(() {
        _mediaItems = items;
        _isLoadingMedia = false;
      });
    }
  }

  Future<void> _queueMedia(MediaItem item) async {
    final success = await apiService.addToQueue(
      chatId: item.chatId,
      messageId: item.messageId,
      title: item.title,
      totalBytes: item.totalBytes,
      channelTitle: _selectedDialog?.title,
    );

    if (success && mounted) {
      context.read<QueueProvider>().refreshQueue();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Added "${item.title}" to high-speed queue!'),
          backgroundColor: AppColors.success,
          duration: const Duration(seconds: 2),
        ),
      );
      // Reload media to update queueStatus badge
      if (_selectedDialog != null) {
        _selectDialog(_selectedDialog!);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final app = context.watch<AppProvider>();
    final isAuthorized = app.status?.isAuthorized ?? false;

    if (!isAuthorized) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: AppColors.surfaceDark,
                  shape: BoxShape.circle,
                  border: Border.all(color: AppColors.borderDark),
                ),
                child: const Icon(Icons.lock_outline, size: 48, color: AppColors.primary),
              ),
              const SizedBox(height: 20),
              const Text(
                'Telegram Account Not Linked',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
              ),
              const SizedBox(height: 8),
              const Text(
                'Link your account to browse private channels, groups, and Saved Messages directly.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 13, color: AppColors.textMuted),
              ),
              const SizedBox(height: 24),
              FilledButton.icon(
                icon: const Icon(Icons.qr_code_2),
                label: const Text('Link Telegram Account'),
                onPressed: () => QrLoginDialog.show(context),
              ),
            ],
          ),
        ),
      );
    }

    final filteredDialogs = _searchQuery.isEmpty
        ? _dialogs
        : _dialogs.where((d) => d.title.toLowerCase().contains(_searchQuery.toLowerCase())).toList();

    return Column(
      children: [
        // Horizontal Chat Selector Strip
        Container(
          color: AppColors.surfaceDark,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Column(
            children: [
              // Search input
              SizedBox(
                height: 38,
                child: TextField(
                  decoration: InputDecoration(
                    hintText: 'Search channels & chats...',
                    prefixIcon: const Icon(Icons.search, size: 18, color: AppColors.textMuted),
                    contentPadding: EdgeInsets.zero,
                    fillColor: AppColors.cardDark,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: BorderSide.none,
                    ),
                  ),
                  onChanged: (val) => setState(() => _searchQuery = val),
                ),
              ),
              const SizedBox(height: 8),
              // Channel Chips
              SizedBox(
                height: 36,
                child: _isLoadingDialogs
                    ? const Center(child: SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)))
                    : ListView.builder(
                        scrollDirection: Axis.horizontal,
                        itemCount: filteredDialogs.length,
                        itemBuilder: (context, index) {
                          final d = filteredDialogs[index];
                          final isSelected = _selectedDialog?.id == d.id;
                          return Padding(
                            padding: const EdgeInsets.only(right: 8),
                            child: FilterChip(
                              label: Text(d.title),
                              selected: isSelected,
                              avatar: Icon(
                                d.isSelf
                                    ? Icons.bookmark
                                    : (d.isChannel ? Icons.campaign : Icons.group),
                                size: 16,
                                color: isSelected ? Colors.white : AppColors.primary,
                              ),
                              selectedColor: AppColors.primary,
                              backgroundColor: AppColors.cardDark,
                              labelStyle: TextStyle(
                                fontSize: 12,
                                fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                                color: isSelected ? Colors.white : AppColors.textPrimary,
                              ),
                              side: BorderSide(
                                color: isSelected ? AppColors.primary : AppColors.borderDark,
                              ),
                              onSelected: (_) => _selectDialog(d),
                            ),
                          );
                        },
                      ),
              ),
            ],
          ),
        ),

        // Media Item List
        Expanded(
          child: _isLoadingMedia
              ? const Center(child: CircularProgressIndicator(color: AppColors.primary))
              : _mediaItems.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.perm_media_outlined, size: 36, color: AppColors.textMuted),
                          const SizedBox(height: 12),
                          Text(
                            _selectedDialog != null
                                ? 'No downloadable media in "${_selectedDialog!.title}"'
                                : 'Select a channel above to browse files',
                            style: const TextStyle(fontSize: 14, color: AppColors.textMuted),
                          ),
                        ],
                      ),
                    )
                  : ListView.builder(
                      itemCount: _mediaItems.length,
                      itemBuilder: (context, index) {
                        final item = _mediaItems[index];
                        final isQueued = item.isQueuedOrDownloading;
                        return Container(
                          margin: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: AppColors.cardDark,
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(color: AppColors.borderDark),
                          ),
                          child: Row(
                            children: [
                              Container(
                                width: 40,
                                height: 40,
                                decoration: BoxDecoration(
                                  color: AppColors.surfaceDark,
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Icon(
                                  item.isVideo
                                      ? Icons.movie_outlined
                                      : (item.isAudio ? Icons.music_note_outlined : Icons.insert_drive_file_outlined),
                                  color: AppColors.primary,
                                  size: 20,
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      item.title,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        fontSize: 13,
                                        fontWeight: FontWeight.w600,
                                        color: AppColors.textPrimary,
                                      ),
                                    ),
                                    const SizedBox(height: 3),
                                    Text(
                                      item.formattedSize,
                                      style: const TextStyle(fontSize: 11, color: AppColors.textMuted),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(width: 8),
                              FilledButton.icon(
                                icon: Icon(
                                  isQueued ? Icons.check : Icons.download,
                                  size: 16,
                                ),
                                label: Text(isQueued ? 'Queued' : 'Download'),
                                style: FilledButton.styleFrom(
                                  backgroundColor: isQueued ? AppColors.surfaceDark : AppColors.primary,
                                  foregroundColor: isQueued ? AppColors.textMuted : Colors.white,
                                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                                ),
                                onPressed: isQueued ? null : () => _queueMedia(item),
                              ),
                            ],
                          ),
                        );
                      },
                    ),
        ),
      ],
    );
  }
}
