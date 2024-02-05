-- initializes the database
-- note: if you're using an older version of python (and thus an older version of sqlite, you may need to remove the "STRICT" part)

CREATE TABLE "Accounts" (
	"Username"	TEXT NOT NULL,
	"PasswordSHA256"	TEXT NOT NULL,
	"FirstName"	TEXT NOT NULL DEFAULT "",
	"LastName"	TEXT NOT NULL DEFAULT "",
	"Address"	TEXT NOT NULL DEFAULT "",
	"CardNumber"	TEXT NOT NULL DEFAULT "",
	"CardExpiry"	TEXT NOT NULL DEFAULT "",
	"CardCode"	TEXT NOT NULL DEFAULT "",
	PRIMARY KEY ("Username")
) STRICT;

CREATE TABLE "Restaurants" (
	"RestaurantID"	INTEGER NOT NULL,
	"Owner"	TEXT NOT NULL,
	"Name"	TEXT NOT NULL,
	"Deleted"	INTEGER NOT NULL DEFAULT FALSE,
	PRIMARY KEY ("RestaurantID" AUTOINCREMENT)
) STRICT;

CREATE TABLE "MenuItems" (
	"ItemID"	INTEGER NOT NULL,
	"RestaurantID"	INTEGER NOT NULL,
	"Name"	TEXT NOT NULL,
	"Price"	INTEGER NOT NULL, -- in cents (sqlite doesn't have fixed-decimal types)
	"Deleted"	INTEGER NOT NULL DEFAULT FALSE,
	PRIMARY KEY ("ItemID" AUTOINCREMENT),
	FOREIGN KEY ("RestaurantID") REFERENCES Restaurants("RestaurantID") ON DELETE CASCADE
) STRICT;

CREATE TABLE "RestaurantEmployees" (
	"RestaurantID" INTEGER NOT NULL,
	"Username" TEXT NOT NULL,
	PRIMARY KEY ("RestaurantID", "Username"),
	FOREIGN KEY ("Username") REFERENCES Accounts("Username") ON DELETE CASCADE,
	FOREIGN KEY ("RestaurantID") REFERENCES Restaurants("RestaurantID") ON DELETE RESTRICT
) STRICT;

CREATE TABLE "Orders" (
	"OrderID" INTEGER NOT NULL,
	"Date" TEXT NOT NULL,
	"RestaurantID" INTEGER NOT NULL,
	"Username" TEXT NOT NULL,
	"Address" TEXT NOT NULL DEFAULT "", -- doesn't get populated for pending orders
	"Total" INTEGER NOT NULL DEFAULT 0, -- in cents (sqlite doesn't have fixed-decimal types)
	"Status" TEXT NOT NULL DEFAULT "PENDING",
	PRIMARY KEY ("OrderID" AUTOINCREMENT),
	FOREIGN KEY ("Username") REFERENCES Accounts("Username") ON DELETE CASCADE,
	FOREIGN KEY ("RestaurantID") REFERENCES Restaurants("RestaurantID") ON DELETE RESTRICT
	
) STRICT;

CREATE TABLE "OrderItems" (
	"OrderID" INTEGER NOT NULL,
	"ItemID"	INTEGER NOT NULL,
	"Quantity" INTEGER NOT NULL DEFAULT 0,
	PRIMARY KEY ("OrderID", "ItemID"),
	FOREIGN KEY ("OrderId") REFERENCES Orders("OrderID") ON DELETE CASCADE,
	FOREIGN KEY ("ItemID") REFERENCES MenuItems("ItemID") ON DELETE RESTRICT
) STRICT;

PRAGMA user_version = 1;
