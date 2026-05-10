import 'package:flutter/material.dart';

import 'core/presentation/main_nav_shell.dart';

void main() {
  runApp(const DetailManagementApp());
}

class DetailManagementApp extends StatelessWidget {
  const DetailManagementApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Family Budget',
      debugShowCheckedModeBanner: false,
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
      home: const MainNavShell(),
    );
  }
}
