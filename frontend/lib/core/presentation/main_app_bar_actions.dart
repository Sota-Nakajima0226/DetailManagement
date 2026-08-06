import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/auth/application/auth_providers.dart';
import '../../features/categories/presentation/categories_page.dart';
import '../../features/fixed_expenses/presentation/fixed_expenses_page.dart';
import '../../features/manual_expenses/presentation/manual_expenses_page.dart';
import '../../features/rules/presentation/rules_page.dart';
import '../../features/upload/presentation/upload_page.dart';

/// 主要画面の AppBar 用。「アップロード」と設定メニュー。
/// 明細一覧から開くときは [uploadTargetYear] / [uploadTargetMonth] で初期年月を渡す。
List<Widget> buildMainAppBarActions(
  BuildContext context,
  WidgetRef ref, {
  int? uploadTargetYear,
  int? uploadTargetMonth,
}) {
  return [
    IconButton(
      tooltip: 'アップロード',
      onPressed: () {
        Navigator.of(context).push(
          MaterialPageRoute<void>(
            builder: (_) => UploadPage(
              initialYear: uploadTargetYear,
              initialMonth: uploadTargetMonth,
            ),
          ),
        );
      },
      icon: const Icon(Icons.upload_file),
    ),
    PopupMenuButton<String>(
      tooltip: 'メニュー',
      onSelected: (value) async {
        if (value == 'logout') {
          await ref.read(authRepositoryProvider).signOut();
          return;
        }
        final routes = <String, Widget>{
          'categories': const CategoriesPage(),
          'rules': const RulesPage(),
          'fixed': const FixedExpensesPage(),
          'manual': const ManualExpensesPage(),
        };
        final page = routes[value];
        if (page == null) return;
        if (!context.mounted) return;
        Navigator.of(context).push(
          MaterialPageRoute<void>(builder: (_) => page),
        );
      },
      itemBuilder: (context) => const [
        PopupMenuItem(value: 'categories', child: Text('カテゴリ管理')),
        PopupMenuItem(value: 'rules', child: Text('分類ルール管理')),
        PopupMenuItem(value: 'fixed', child: Text('固定費管理')),
        PopupMenuItem(value: 'manual', child: Text('手動支払い登録')),
        PopupMenuDivider(),
        PopupMenuItem(value: 'logout', child: Text('ログアウト')),
      ],
    ),
  ];
}
