import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/main.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const TelegramDownloaderApp());
    expect(find.text('Telegram Downloader'), findsOneWidget);
  });
}
