import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/auth/application/auth_providers.dart';
import '../../features/auth/presentation/login_page.dart';
import '../../features/upload/presentation/upload_page.dart';
import '../navigation/app_location.dart';
import 'main_nav_shell.dart';

/// 未ログイン時は [LoginPage]、ログイン済みはパスに応じた画面を表示する。
class AuthGate extends ConsumerWidget {
  const AuthGate({
    super.key,
    required this.location,
  });

  final AppLocation location;

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
        if (location.showsUpload) {
          return UploadPage(
            initialYear: location.year,
            initialMonth: location.month,
          );
        }
        return const MainNavShell();
      },
    );
  }
}
