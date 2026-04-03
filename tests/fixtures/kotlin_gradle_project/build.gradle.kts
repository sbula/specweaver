plugins {
    kotlin("jvm") version "1.9.10"
    id("io.gitlab.arturbosch.detekt") version "1.23.1"
}

repositories {
    mavenCentral()
}

dependencies {
    testImplementation(kotlin("test"))
}

tasks.test {
    useJUnitPlatform()
}

detekt {
    buildUponDefaultConfig = true
    config.setFrom(files("$projectDir/detekt.yml"))
    reports {
        sarif.required.set(true)
    }
}
