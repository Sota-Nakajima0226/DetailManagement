class CategoryItem {
  CategoryItem({
    required this.id,
    required this.name,
    required this.color,
    required this.sortOrder,
  });

  final int id;
  final String name;
  final String color;
  final int sortOrder;

  factory CategoryItem.fromJson(Map<String, dynamic> json) {
    return CategoryItem(
      id: json['id'] as int,
      name: json['name'] as String,
      color: json['color'] as String? ?? '#888888',
      sortOrder: json['sort_order'] as int? ?? 0,
    );
  }
}
