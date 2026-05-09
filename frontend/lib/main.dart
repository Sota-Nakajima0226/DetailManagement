import 'package:flutter/material.dart';

import 'features/statements/presentation/statements_list_page.dart';

void main() {
  runApp(const DetailManagementApp());
}

class DetailManagementApp extends StatelessWidget {
  const DetailManagementApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Family Budget',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal),
        useMaterial3: true,
      ),
      home: const StatementsListPage(),
    );
  }
}
