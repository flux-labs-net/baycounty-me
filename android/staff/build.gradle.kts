// BayCounty.me Staff: the government workspace (/staff) for city and county staff and the site owner, through
// /api/gov. A separate app from the resident one (so residents never get staff screens); shares :kit. Mirrors ios/BayCountyStaff.
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("app.cash.paparazzi")
}

android {
    namespace = "me.baycounty.staff"
    compileSdk = 36

    defaultConfig {
        applicationId = "me.baycounty.staff"
        minSdk = 26
        targetSdk = 36
        versionCode = System.getenv("BCM_VERSION_CODE")?.toIntOrNull() ?: 1
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
    buildFeatures { compose = true; buildConfig = true }
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
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.fragment:fragment-ktx:1.8.5")
    implementation("androidx.biometric:biometric:1.1.0")
    implementation("org.osmdroid:osmdroid-android:6.1.20")  // maps on alerts (drop pins where it applies)
    testImplementation("junit:junit:4.13.2")
}

tasks.withType<Test>().configureEach {
    System.getProperty("fullres")?.let { systemProperty("fullres", it) }
    reports.html.required.set(false)
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        optIn.addAll("androidx.compose.material3.ExperimentalMaterial3Api", "androidx.compose.foundation.layout.ExperimentalLayoutApi")
    }
}
