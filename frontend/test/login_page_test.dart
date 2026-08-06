import 'package:detail_management/features/auth/presentation/login_page.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('login button is disabled while validation fails on empty fields',
      (tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: LoginPage()),
      ),
    );

    await tester.tap(find.widgetWithText(FilledButton, 'ログイン'));
    await tester.pump();

    expect(find.text('メールアドレスを入力してください'), findsOneWidget);
    expect(find.text('パスワードを入力してください'), findsOneWidget);
  });

  testWidgets('shows email format validation error', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: LoginPage()),
      ),
    );

    await tester.enterText(
      find.widgetWithText(TextFormField, 'メールアドレス'),
      'not-an-email',
    );
    await tester.enterText(
      find.widgetWithText(TextFormField, 'パスワード'),
      'password',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'ログイン'));
    await tester.pump();

    expect(find.text('メールアドレスの形式が正しくありません'), findsOneWidget);
  });
}
