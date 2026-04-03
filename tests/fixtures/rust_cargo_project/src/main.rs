fn main() {
    println!("Hello, world!");
}

fn lint_error() {
    let x = 3.14f32;
    if x == std::f32::NAN {
        println!("This is a clippy cmp_nan error");
    }
}

fn complex_logic(x: i32) -> i32 {
    let mut sum = 0;
    if x > 0 { sum += 1; }
    if x > 1 { sum += 1; }
    if x > 2 { sum += 1; }
    if x > 3 { sum += 1; }
    if x > 4 { sum += 1; }
    if x > 5 { sum += 1; }
    if x > 6 { sum += 1; }
    if x > 7 { sum += 1; }
    if x > 8 { sum += 1; }
    if x > 9 { sum += 1; }
    if x > 10 { sum += 1; }
    if x > 11 { sum += 1; }
    if x > 12 { sum += 1; }
    if x > 13 { sum += 1; }
    if x > 14 { sum += 1; }
    sum
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_success() {
        assert_eq!(2 + 2, 4);
    }
}
