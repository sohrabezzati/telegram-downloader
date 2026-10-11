class ChatDialog {
  final int id;
  final String title;
  final bool isChannel;
  final bool isGroup;
  final bool isUser;
  final bool isSelf;
  final int unreadCount;

  ChatDialog({
    required this.id,
    required this.title,
    required this.isChannel,
    required this.isGroup,
    required this.isUser,
    required this.isSelf,
    required this.unreadCount,
  });

  factory ChatDialog.fromJson(Map<String, dynamic> json) {
    return ChatDialog(
      id: json['id'] as int? ?? 0,
      title: json['title'] as String? ?? 'Unnamed Chat',
      isChannel: json['is_channel'] as bool? ?? false,
      isGroup: json['is_group'] as bool? ?? false,
      isUser: json['is_user'] as bool? ?? false,
      isSelf: json['is_self'] as bool? ?? false,
      unreadCount: json['unread_count'] as int? ?? 0,
    );
  }
}
