plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
    id("app.cash.paparazzi")
}

android {
    namespace = "me.baycounty.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "me.baycounty"  // the Play listing's package name (fixed once set); the code namespace stays me.baycounty.app
        minSdk = 26
        targetSdk = 36
        // Play rejects a versionCode it already has. The release workflow sets BCM_VERSION_CODE to its run number. About shows both.
        versionCode = System.getenv("BCM_VERSION_CODE")?.toIntOrNull() ?: 1
        versionName = "1.0"
        // Firebase Cloud Messaging for phone alerts, from CI secrets (never the repo). Blank = alerts off in this build.
        for (k in listOf("FCM_APP_ID", "FCM_API_KEY", "FCM_PROJECT_ID", "FCM_SENDER_ID")) {
            buildConfigField("String", k, "\"" + (System.getenv(k) ?: "") + "\"")
        }
    }

    signingConfigs {
        // Release signing comes from environment variables (CI secrets), never from the repo. See android/README.md.
        create("release") {
            val ks = System.getenv("BCM_KEYSTORE")
            if (ks != null) {
                storeFile = file(ks)
                storePassword = System.getenv("BCM_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("BCM_KEY_ALIAS") ?: "upload"
                keyPassword = System.getenv("BCM_KEY_PASSWORD") ?: System.getenv("BCM_KEYSTORE_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            if (System.getenv("BCM_KEYSTORE") != null) signingConfig = signingConfigs.getByName("release")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

dependencies {
    implementation(project(":kit"))
    val bom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(bom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.core:core-splashscreen:1.0.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.browser:browser:1.8.0")
    implementation("org.osmdroid:osmdroid-android:6.1.20")
    implementation("com.google.firebase:firebase-messaging:24.1.0")
    testImplementation("junit:junit:4.13.2")
}

tasks.withType<Test>().configureEach {
    systemProperty("repoRoot", rootProject.projectDir.parentFile.absolutePath)
    System.getProperty("screens")?.let { systemProperty("screens", it) }
    System.getProperty("pages")?.let { systemProperty("pages", it) }
    System.getProperty("fullres")?.let { systemProperty("fullres", it) }
    System.getProperty("tall")?.let { systemProperty("tall", it) }
    // Paparazzi 2.0 alphas build their HTML report with a Gradle class that 8.x lacks. The PNGs and the XML results
    // are what CI uses, so the HTML report stays off.
    reports.html.required.set(false)
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        optIn.addAll("androidx.compose.foundation.layout.ExperimentalLayoutApi", "androidx.compose.material3.ExperimentalMaterial3Api", "androidx.compose.foundation.ExperimentalFoundationApi")
    }
}
