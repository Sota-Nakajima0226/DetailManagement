import 'package:flutter/material.dart';

import '../../features/categories/presentation/categories_page.dart';
import '../../features/fixed_expenses/presentation/fixed_expenses_page.dart';
import '../../features/manual_expenses/presentation/manual_expenses_page.dart';
import '../../features/rules/presentation/rules_page.dart';
import '../../features/upload/presentation/upload_page.dart';

/// 主要画面（明細一覧・グラフ集計など）の AppBar に共通で表示するアクション群。
/// 「アップロード」ボタンと「設定系メニュー」の3点リーダーを返す。
List<Widget> buildMainAppBarActions(BuildContext context) {
  return [
    IconButton(
      tooltip: 'アップロード',
      onPressed: () {
        Navigator.of(context).push(
          MaterialPageRoute<void>(builder: (_) => const UploadPage()),
        );
      },
      icon: const Icon(Icons.upload_file),
    ),
    PopupMenuButton<String>(
      tooltip: 'メニュー',
      onSelected: (value) {
        final routes = <String, Widget>{
          'categories': const CategoriesPage(),
          'rules': const RulesPage(),
          'fixed': const FixedExpensesPage(),
          'manual': const ManualExpensesPage(),
        };
        final page = routes[value];
        if (page == null) return;
        Navigator.of(context).push(
          MaterialPageRoute<void>(builder: (_) => page),
        );
      },
      itemBuilder: (context) => const [
        PopupMenuItem(value: 'categories', child: Text('カテゴリ管理')),
        PopupMenuItem(value: 'rules', child: Text('分類ルール管理')),
        PopupMenuItem(value: 'fixed', child: Text('固定費管理')),
        PopupMenuItem(value: 'manual', child: Text('手動支払い登録')),
      ],
    ),
  ];
}
