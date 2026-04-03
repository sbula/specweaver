fun getGreeting(): String {
    val unusedVar = 42 // Detekt error intentionally
    return "Hello Kotlin World!"
}

fun complexLogic(n: Int) {
    if (n == 1) println("1")
    else if (n == 2) println("2")
    else if (n == 3) println("3")
    else if (n == 4) println("4")
    else if (n == 5) println("5")
    else if (n == 6) println("6")
    else if (n == 7) println("7")
    else if (n == 8) println("8")
    else if (n == 9) println("9")
    else if (n == 10) println("10")
    else if (n == 11) println("11")
    else if (n == 12) println("12")
    else if (n == 13) println("13")
    else if (n == 14) println("14")
    else println("15") // Intentional high complexity 15
}

fun main() {
    println(getGreeting())
}
