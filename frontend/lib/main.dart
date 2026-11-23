import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'core/config/app_config.dart';
import 'core/navigation/app_route.dart';
import 'core/navigation/url_strategy.dart';
import 'core/network/api_client.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  configurePathUrlStrategy();

  if (!AppConfig.isSupabaseConfigured) {
    runApp(const _ConfigErrorApp());
    return;
  }

  await Supabase.initialize(
    url: AppConfig.supabaseUrl,
    anonKey: AppConfig.supabaseAnonKey,
  );

  runApp(
    const ProviderScope(
      child: DetailManagementApp(),
    ),
  );
}

class DetailManagementApp extends StatelessWidget {
  const DetailManagementApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Family Budget',
      debugShowCheckedModeBanner: false,
      scaffoldMessengerKey: ApiClient.scaffoldMessengerKey,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal),
        useMaterial3: true,
        appBarTheme: const AppBarTheme(
          toolbarHeight: 48,
          titleTextStyle: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      onGenerateRoute: buildAppRoute,
      onGenerateInitialRoutes: buildInitialAppRoutes,
    );
  }
}

class _ConfigErrorApp extends StatelessWidget {
  const _ConfigErrorApp();

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      home: Scaffold(
        body: Center(
          child: Padding(
            padding: EdgeInsets.all(24),
            child: Text(
              'Supabase の設定がありません。\n'
              'frontend/.env に SUPABASE_URL と SUPABASE_ANON_KEY を設定し、'
              'scripts/dev.sh で起動してください。',
              textAlign: TextAlign.center,
            ),
          ),
        ),
      ),
    );
  }
}
