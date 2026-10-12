// The Android app: Python (Chaquopy) runs tools/launcher.py's local server in-process, a full-screen WebView
// shows the setup page and then the player. tools/ and web/ are copied from the repo into the APK's assets.
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "io.github.jalenlin.danmemo"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.github.jalenlin.danmemo"
        minSdk = 24
        targetSdk = 35
        versionCode = (project.findProperty("versionCode") as String?)?.toInt() ?: 1
        versionName = (project.findProperty("versionName") as String?) ?: "1.0.0"
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }  // phones; the emulator
    }

    signingConfigs {
        // release signing from the environment (CI secrets); without it the release build is left unsigned
        System.getenv("DANMEMO_KEYSTORE")?.takeIf { it.isNotBlank() }?.let { ks ->
            create("release") {
                storeFile = file(ks)
                storePassword = System.getenv("DANMEMO_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("DANMEMO_KEY_ALIAS")
                keyPassword = System.getenv("DANMEMO_KEY_PASSWORD")
            }
        }
    }
    buildTypes {
        debug { applicationIdSuffix = ".debug" }  // installs next to the release app
        release {
            isMinifyEnabled = false
            signingConfigs.findByName("release")?.let { signingConfig = it }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    sourceSets["main"].assets.srcDir(layout.buildDirectory.dir("generated/player"))
    // ffmpeg for the cutscene movies (android/ffmpeg/build.sh); unpacked on install so it can be run
    sourceSets["main"].jniLibs.srcDir(rootProject.file("ffmpeg/out"))
    packaging { jniLibs { useLegacyPackaging = true } }
}

chaquopy {
    defaultConfig {
        version = "3.12"
        pip {
            install("pycryptodome")
            install("pyelftools")
            install("pillow")
        }
    }
}

// tools/*.py + launcher.html and the player's own web files (not built data) -> assets/app/
val copyPlayer by tasks.registering(Sync::class) {
    val repo = rootProject.projectDir.parentFile
    from(File(repo, "tools")) { include("*.py", "launcher.html"); into("app/tools") }
    from(File(repo, "web")) { include("index.html", "transparent.png", "js/**", "css/**", "vendor/**"); into("app/web") }
    from(File(repo, "LICENSE")) { into("app") }
    from(File(repo, "android/ffmpeg/license")) { into("app/licenses/ffmpeg") }
    into(layout.buildDirectory.dir("generated/player"))
}
tasks.named("preBuild") { dependsOn(copyPlayer) }

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-ktx:1.9.3")
}
