package com.example;

public class App {
    private int unusedField = 42; // Intentionally unused for PMD error

    public String getGreeting() {
        return "Hello World!";
    }

    public void complexLogic(int n) { // Intentional high complexity
        if (n == 1) { System.out.println("1"); }
        else if (n == 2) { System.out.println("2"); }
        else if (n == 3) { System.out.println("3"); }
        else if (n == 4) { System.out.println("4"); }
        else if (n == 5) { System.out.println("5"); }
        else if (n == 6) { System.out.println("6"); }
        else if (n == 7) { System.out.println("7"); }
        else if (n == 8) { System.out.println("8"); }
        else if (n == 9) { System.out.println("9"); }
        else if (n == 10) { System.out.println("10"); }
        else if (n == 11) { System.out.println("11"); }
        else if (n == 12) { System.out.println("12"); }
        else if (n == 13) { System.out.println("13"); }
        else if (n == 14) { System.out.println("14"); }
        else if (n == 15) { System.out.println("15"); }
    }

    public static void main(String[] args) {
        System.out.println(new App().getGreeting());
    }
}
