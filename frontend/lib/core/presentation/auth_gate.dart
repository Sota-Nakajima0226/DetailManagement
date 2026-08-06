import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/auth/application/auth_providers.dart';
import '../../features/auth/presentation/login_page.dart';
import 'main_nav_shell.dart';

/// 未ログイン時は [LoginPage]、ログイン済みは [MainNavShell] を表示する。
class AuthGate extends ConsumerWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authStateChangesProvider);

    return authState.when(
      loading: () => const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      ),
      error: (error, _) => Scaffold(
        body: Center(child: Text('認証の初期化に失敗しました: $error')),
      ),
      data: (state) {
        final session = state.session;
        if (session == null) {
          return const LoginPage();
        }
        return const MainNavShell();
      },
    );
  }
}
