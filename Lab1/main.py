import json
import xml.etree.ElementTree as ET
from typing import List


# ИСКЛЮЧЕНИЯ
class ProductNotFoundError(Exception):
    """Ошибка: товар не найден"""

class CustomerNotFoundError(Exception):
    """Ошибка: покупатель не найден"""

class InsufficientStockError(Exception):
    """Ошибка: недостаточно товара на складе"""


# МОДЕЛИ
class Product:
    """Класс описывает товар в интернет-магазине"""

    def __init__(self, id: int, name: str, category: str, price: float, stock: int):
        self.id = id
        self.name = name
        self.category = category
        self.price = price
        self.stock = stock

    # обновление наличия
    def update_stock(self, quantity: int) -> None:
        if self.stock + quantity < 0:
            raise InsufficientStockError(f"Недостаточно товара '{self.name}' на складе.")
        self.stock += quantity

    # объект в словарь (для json и xml)
    def to_dict(self) -> dict:
        return vars(self)

    # словарь в объект(для json и xml)
    @staticmethod
    def from_dict(data: dict) -> "Product":
        return Product(**data)


class Customer:
    """Класс описывает покупателя в интернет-магазине"""

    def __init__(self, id: int, name: str, email: str, address: str):
        self.id = id
        self.name = name
        self.email = email
        self.address = address

    def to_dict(self) -> dict:
        return vars(self)

    @staticmethod
    def from_dict(data: dict) -> "Customer":
        return Customer(**data)


class CartItem:
    """Класс описывает один элемент корзины в интернет-магазине (товар+кол-во)"""

    def __init__(self, product: Product, quantity: int):
        self.product = product
        self.quantity = quantity

    def subtotal(self) -> float:
        return self.product.price * self.quantity


class ShoppingCart:
    """Класс описывает корзину в интернет-магазине (товар+кол-во)"""

    def __init__(self, customer: Customer):
        self.customer = customer
        self.items: List[CartItem] = []

    def add_item(self, product: Product, quantity: int) -> None:
        for item in self.items:
            if item.product.id == product.id:
                item.quantity += quantity
                return
        self.items.append(CartItem(product, quantity))

    def remove_item(self, product_id: int) -> None:
        self.items = [i for i in self.items if i.product.id != product_id]

    def total_price(self) -> float:
        return sum(i.subtotal() for i in self.items)


class Order:
    """Класс описывает заказ в интернет-магазине"""
    def __init__(self, id: int, customer: Customer, items: List[CartItem]):
        self.id = id
        self.customer = customer
        self.items = items
        self.status = "Создан"
        self.total = sum(item.subtotal() for item in items)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_id": self.customer.id,
            "items": [{"product_id": i.product.id, "quantity": i.quantity} for i in self.items],
            "status": self.status,
            "total": self.total
        }

    @staticmethod
    def from_dict(data: dict, customers: List[Customer], products: List[Product]) -> "Order":
        customer = next(c for c in customers if c.id == data["customer_id"])
        items = []
        for i in data["items"]:
            product = next(p for p in products if p.id == i["product_id"])
            items.append(CartItem(product, i["quantity"]))
        order = Order(data["id"], customer, items)
        order.status = data.get("status", "Создан")
        order.total = data.get("total", sum(i.subtotal() for i in items))
        return order
    

class Payment:
    """Информация об оплате"""
    def __init__(self, order_id: int, amount: float, method: str, status: str = "Ожидание"):
        self.order_id = order_id
        self.amount = amount
        self.method = method
        self.status = status

    def to_dict(self) -> dict:
        return vars(self)
    
    @staticmethod
    def from_dict(data: dict) -> "Payment":
        return Payment(**data)


class Delivery:
    """Информация о доставке"""
    def __init__(self, order_id: int, address: str, status: str = "Не отправлено"):
        self.order_id = order_id
        self.address = address
        self.status = status

    def to_dict(self) -> dict:
        return vars(self)
    
    @staticmethod
    def from_dict(data: dict) -> "Delivery":
        return Delivery(**data)
    

class Review:
    """Отзыв покупателя о товаре"""

    def __init__(self, id: int, product_id: int, customer_id: int, rating: int, comment: str):
        self.id = id
        self.product_id = product_id
        self.customer_id = customer_id
        self.rating = rating  # Оценка от 1 до 5
        self.comment = comment

    def to_dict(self) -> dict:
        return vars(self)
    
    @staticmethod
    def from_dict(data: dict) -> "Review":
        return Review(**data)
    

class Category:
    """Категория товаров"""

    def __init__(self, id: int, name: str, description: str = ""):
        self.id = id
        self.name = name
        self.description = description

    def to_dict(self) -> dict:
        return vars(self)

    @staticmethod
    def from_dict(data: dict) -> "Category":
        return Category(**data)

    


# ---------- Менеджер магазина ----------
class StoreManager:
    """Главный класс управления интернет-магазином"""
    def __init__(self):
        self.products: List[Product] = []
        self.customers: List[Customer] = []
        self.categories: List[Category] = []
        self.orders: List[Order] = []
        self.payments: List[Payment] = []
        self.deliveries: List[Delivery] = []
        self.reviews: List[Review] = []

    # --- CRUD: товары ---
    def add_product(self, product: Product) -> None:
        self.products.append(product)

    def find_product(self, product_id: int) -> Product:
        for p in self.products:
            if p.id == product_id:
                return p
        raise ProductNotFoundError(f"Товар с ID {product_id} не найден.")

    def update_product(self, product_id: int, **kwargs) -> None:
        product = self.find_product(product_id)
        for k, v in kwargs.items():
            if hasattr(product, k):
                setattr(product, k, v)

    def remove_product(self, product_id: int) -> None:
        self.products = [p for p in self.products if p.id != product_id]

    # --- Категории ---

    def add_category(self, category: Category):
        self.categories.append(category)


    # --- CRUD: клиенты ---
    def add_customer(self, customer: Customer) -> None:
        self.customers.append(customer)

    def find_customer(self, customer_id: int) -> Customer:
        for c in self.customers:
            if c.id == customer_id:
                return c
        raise CustomerNotFoundError(f"Покупатель с ID {customer_id} не найден.")

    # --- Заказы ---
    def create_order(self, customer_id: int, cart: ShoppingCart) -> Order:
        customer = self.find_customer(customer_id)
        for item in cart.items:
            item.product.update_stock(-item.quantity)
        order = Order(len(self.orders) + 1, customer, cart.items)
        self.orders.append(order)
        return order

    # --- Отзывы ---
    def add_review(self, review: Review) -> None:
        self.reviews.append(review)

    # --- Оплата ---
    def add_payment(self, payment: Payment) -> None: 
        self.payments.append(payment)

    # --- Доставка ---
    def add_delivery(self, delivery: Delivery) -> None:
        self.deliveries.append(delivery)

    # --- Сохранение / загрузка JSON ---
    def save_to_json(self, filename: str) -> None:
        data = {
            "products": [p.to_dict() for p in self.products],
            "customers": [c.to_dict() for c in self.customers],
            "categories": [c.to_dict() for c in self.categories],
            "orders": [o.to_dict() for o in self.orders],
            "payments": [p.to_dict() for p in self.payments],
            "deliveries": [d.to_dict() for d in self.deliveries],
            "reviews": [r.to_dict() for r in self.reviews],
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)


    def load_from_json(self, filename: str) -> None:
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.products = [Product.from_dict(p) for p in data.get("products", [])]
            self.customers = [Customer.from_dict(c) for c in data.get("customers", [])]
            self.categories = [Category.from_dict(c) for c in data.get("categories", [])]
            self.orders = [Order.from_dict(o, self.customers, self.products) for o in data.get("orders", [])]
            self.payments = [Payment.from_dict(p) for p in data.get("payments", [])]
            self.deliveries = [Delivery.from_dict(d) for d in data.get("deliveries", [])]
            self.reviews = [Review.from_dict(r) for r in data.get("reviews", [])]

        except FileNotFoundError:
            print(f"Файл {filename} не найден. Загружается пустой магазин.")


    def save_to_xml(self, filename: str):
        root = ET.Element("store")
        for key, items in [("products", self.products),
                           ("customers", self.customers),
                           ("categories", self.categories),
                           ("orders", self.orders),
                           ("payments", self.payments),
                           ("deliveries", self.deliveries),
                           ("reviews", self.reviews)]:
            section = ET.SubElement(root, key)
            for item in items:
                el = ET.SubElement(section, key[:-1])
                for k, v in item.to_dict().items():
                    sub = ET.SubElement(el, k)
                    if isinstance(v, (dict, list)):
                        sub.text = json.dumps(v, ensure_ascii=False)
                    else:
                        sub.text = str(v)
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        tree.write(filename, encoding="utf-8", xml_declaration=True)


    def load_from_xml(self, filename: str):
        try:
            tree = ET.parse(filename)
            root = tree.getroot()

            def parse_section(tag):
                """Извлекает список элементов раздела XML в виде словарей"""
                items = []
                section = root.find(tag)
                if section is not None:
                    for el in section:
                        data = {child.tag: child.text for child in el}
                        items.append(data)
                return items

            def to_int(value):
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return value

            def to_float(value):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return value

            # --- Загрузка объектов ---
            self.products = [
                Product(
                    id=to_int(d.get("id")),
                    name=d.get("name", ""),
                    category=d.get("category", ""),
                    price=to_float(d.get("price")),
                    stock=to_int(d.get("stock")),
                )
                for d in parse_section("products")
            ]

            self.customers = [
                Customer(
                    id=to_int(d.get("id")),
                    name=d.get("name", ""),
                    email=d.get("email", ""),
                    address=d.get("address", ""),
                )
                for d in parse_section("customers")
            ]

            self.categories = [Category.from_dict(d) for d in parse_section("categories")]

            # --- Восстановление заказов ---
            self.orders = []
            for d in parse_section("orders"):
                order_data = {
                    "id": to_int(d.get("id")),
                    "customer_id": to_int(d.get("customer_id")),
                    "items": json.loads(d.get("items", "[]")),
                    "status": d.get("status", "Создан"),
                    "total": to_float(d.get("total", 0)),
                }
                try:
                    order = Order.from_dict(order_data, self.customers, self.products)
                    self.orders.append(order)
                except StopIteration:
                    print(f"Ошибка восстановления заказа ID {order_data['id']}: клиент или товар не найден")

            # --- Оплаты ---
            self.payments = [
                Payment(
                    order_id=to_int(d.get("order_id")),
                    amount=to_float(d.get("amount")),
                    method=d.get("method", ""),
                    status=d.get("status", "Ожидание"),
                )
                for d in parse_section("payments")
            ]

            # --- Доставки ---
            self.deliveries = [
                Delivery(
                    order_id=to_int(d.get("order_id")),
                    address=d.get("address", ""),
                    status=d.get("status", "Не отправлено"),
                )
                for d in parse_section("deliveries")
            ]

            # --- Отзывы ---
            self.reviews = [
                Review(
                    id=to_int(d.get("id")),
                    product_id=to_int(d.get("product_id")),
                    customer_id=to_int(d.get("customer_id")),
                    rating=to_int(d.get("rating")),
                    comment=d.get("comment", ""),
                )
                for d in parse_section("reviews")
            ]

            print(f"Данные успешно загружены из файла '{filename}'")

        except FileNotFoundError:
            print(f"Файл '{filename}' не найден.")
        except ET.ParseError:
            print(f"Ошибка чтения XML-файла '{filename}'. Проверьте структуру XML.")


# ---------- Пример использования ----------
if __name__ == "__main__":
    store = StoreManager()

    store.add_category(Category(1, "Ноутбуки"))
    store.add_category(Category(2, "Телефоны"))
    store.add_category(Category(3, "Аксессуары"))

    # --- Добавляем товары и покупателей ---
    store.add_product(Product(1, "Ноутбук Lenovo", "Ноутбуки", 85000.0, 5))
    store.add_product(Product(2, "Смартфон Samsung", "Телефоны", 55000.0, 10))
    store.add_product(Product(3, "Наушники Sony", "Аксессуары", 12000.0, 15))
    store.add_customer(Customer(1, "Тимофей Мальцев", "fala@gmail.com", "Москва, ул. Ташкентская 32/156"))
    store.add_customer(Customer(2, "Олег Мандриков", "penza777@mail.ru", "Пенза, ул. Пушкина"))


    # --- Обновляем товар ---
    store.update_product(3, price=11000.0, stock=20)
    print("\nОбновленный товар:", store.find_product(3).to_dict())

    # --- Создаем корзину ---
    cart = ShoppingCart(store.find_customer(1))
    cart.add_item(store.find_product(1), 1)
    cart.add_item(store.find_product(2), 2)

    # --- Создаем заказ ---
    try:
        order = store.create_order(1, cart)
        print(f"\nЗаказ №{order.id} успешно создан. Сумма: {order.total} руб.")
    except (ProductNotFoundError, CustomerNotFoundError, InsufficientStockError) as e:
        print("Ошибка при создании заказа:", e)

    # --- Оплата заказа ---
    payment = Payment(order_id=order.id, amount=order.total, method="Карта")
    payment.status = "Оплачено"
    store.add_payment(payment)
    print("\nИнформация об оплате:", payment.to_dict())

    # --- Доставка заказа ---
    delivery = Delivery(order_id=order.id, address=order.customer.address)
    delivery.status = "Отправлено"
    store.add_delivery(delivery)
    print("\nИнформация о доставке:", delivery.to_dict())

    store.add_review(Review(1, 1, 1, 5, "Отличный ноутбук!"))

    # --- Сохраняем и загружаем данные ---
    store.save_to_json("store.json")
    store.save_to_xml("store.xml")
    print("\nДанные сохранены в файлы store.json и store.xml.")

    # --- Пробуем загрузить обратно ---
    print("\nЗагрузка данных из JSON:")
    store2 = StoreManager()
    store2.load_from_json("store.json")
    for p in store2.products:
        print(p.to_dict())
    
    print("\nЗагрузка данных из XML:")
    store3 = StoreManager()
    store3.load_from_xml("store.xml")
    for p in store3.products:
        print(p.to_dict())

        # --- Удаляем товар ---
    print("\nДо удаления:")
    for p in store3.products:
        print(p.to_dict())
    store3.remove_product(2)
    print("\nСписок товаров после удаления:")
    for p in store3.products:
        print(p.to_dict())

    # --- Проверим обработку ошибок ---
    print("\nПроверка исключений:")
    try:
        store.find_product(99)
    except ProductNotFoundError as e:
        print("Ошибка:", e)

    store.find_product(99)
    