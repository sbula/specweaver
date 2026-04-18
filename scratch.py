from proto_schema_parser.parser import Parser

ast = Parser().parse("this is bad syntax {")
print(ast)
