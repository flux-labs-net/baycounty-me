// BayCounty.me for Wear OS: today's alerts, the saved home's trash day, the beach flag and the next meeting, plus a
// watch face complication. Shares :kit with the phone app. Mirrors ios/BayCountyWatch.
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("app.cash.paparazzi")
}

android {
    namespace = "me.baycounty.wear"
    compileSdk = 36

    defaultConfig {
        // Same package as the phone app (Play listing me.baycounty): Wear OS only links a watch app to the phone app
        // with the same package name and signing key, and Play ships it as the listing's Wear OS build.
        applicationId = "me.baycounty"
        minSdk = 30
        targetSdk = 36
        // Play needs a different versionCode from the phone build of the same package, so the watch adds 100000.
        versionCode = (System.getenv("BCM_VERSION_CODE")?.toIntOrNull() ?: 1) + 100000
        versionName = "1.0"
    }

    signingConfigs {
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
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "../app/proguard-rules.pro")
            if (System.getenv("BCM_KEYSTORE") != null) signingConfig = signingConfigs.getByName("release")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures { compose = true }
    packaging { resources.excludes += "/META-INF/{AL2.0,LGPL2.1}" }
}

dependencies {
    implementation(project(":kit"))
    implementation("androidx.wear.compose:compose-material3:1.5.0")
    implementation("androidx.wear.compose:compose-foundation:1.5.0")
    implementation("androidx.wear.compose:compose-navigation:1.5.0")
    implementation("androidx.compose.material:material-icons-extended:1.7.8")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("com.google.android.gms:play-services-wearable:19.0.0")
    implementation("androidx.wear.watchface:watchface-complications-data-source-ktx:1.2.1")
    testImplementation("junit:junit:4.13.2")
}

tasks.withType<Test>().configureEach {
    System.getProperty("fullres")?.let { systemProperty("fullres", it) }
    reports.html.required.set(false)
}

kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }
