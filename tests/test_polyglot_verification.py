from core.verification.deterministic_gates import validate_syntax


def test_python_syntax_validation():
    valid = "def greet(name: str) -> str:\n    return f'Hello, {name}'\n"
    assert validate_syntax(valid, "python").passed is True

    invalid = "def broken(\n    return 42\n"
    res = validate_syntax(invalid, "python")
    assert res.passed is False
    assert any("SyntaxError" in issue for issue in res.issues)


def test_typescript_javascript_syntax_validation():
    valid_ts = """
    interface User {
        id: string;
        name: string;
    }
    export function getUser(id: string): Promise<User> {
        // Line comment
        /* Multi
           line */
        const query = `SELECT * FROM users WHERE id = '${id}'`;
        return fetch(`/api/users/${id}`).then(r => r.json());
    }
    """
    assert validate_syntax(valid_ts, "typescript").passed is True
    assert validate_syntax(valid_ts, "ts").passed is True

    invalid_ts = "function broken() { if (x > 0) { console.log('bad'); }"
    res = validate_syntax(invalid_ts, "typescript")
    assert res.passed is False
    assert any("Unclosed bracket" in issue for issue in res.issues)


def test_rust_syntax_validation():
    valid_rust = """
    // Rust function
    pub fn calculate_hash(data: &[u8]) -> String {
        let mut hasher = DefaultHasher::new();
        hasher.write(data);
        /* Format hash as hex */
        format!("{:x}", hasher.finish())
    }
    """
    assert validate_syntax(valid_rust, "rust").passed is True
    assert validate_syntax(valid_rust, "rs").passed is True

    invalid_rust = "fn broken(a: i32) -> i32 { if a > 0 { a * 2 ]"
    res = validate_syntax(invalid_rust, "rust")
    assert res.passed is False
    assert any("Mismatched bracket" in issue for issue in res.issues)


def test_go_syntax_validation():
    valid_go = """
    package main

    import "fmt"

    func main() {
        // Go greeting
        msg := `Multi-line
                raw string in Go`
        fmt.Println(msg)
    }
    """
    assert validate_syntax(valid_go, "go").passed is True
    assert validate_syntax(valid_go, "golang").passed is True

    invalid_go = "func broken() { fmt.Println('unterminated) }"
    res = validate_syntax(invalid_go, "go")
    assert res.passed is False


def test_java_syntax_validation():
    valid_java = """
    package com.example.service;

    public class UserService {
        private final String apiUrl;

        public UserService(String apiUrl) {
            this.apiUrl = apiUrl;
        }

        public String getApiUrl() {
            return this.apiUrl;
        }
    }
    """
    assert validate_syntax(valid_java, "java").passed is True

    invalid_java = "public class Broken { public void test() { System.out.println(\"hello\"); }"
    res = validate_syntax(invalid_java, "java")
    assert res.passed is False
    assert any("Unclosed bracket" in issue for issue in res.issues)


def test_json_and_sql_validation():
    valid_json = '{"name": "elite-verify", "tools": 3, "proven": true}'
    assert validate_syntax(valid_json, "json").passed is True

    invalid_json = '{"name": "elite-verify", "tools": 3,}'
    assert validate_syntax(invalid_json, "json").passed is False

    valid_sql = "SELECT id, name, created_at FROM users WHERE active = 1 ORDER BY created_at DESC"
    assert validate_syntax(valid_sql, "sql").passed is True

    invalid_sql = "SELECT FROM WHERE"
    assert validate_syntax(invalid_sql, "sql").passed is False
